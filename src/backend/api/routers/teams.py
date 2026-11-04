"""Команды и группы обучающихся."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.access import course_access
from backend.api.dependencies import AuthUser, Connection, check_is_teacher_or_admin
from backend.api.errors import PROTECTED_ERRORS
from backend.db import methods
from backend.schemas.api import CourseMemberResponse
from backend.schemas.data import TeamCreateRequest, TeamResponse, TeamUpdateRequest
from backend.schemas.identity import SuccessResponse

router = APIRouter(tags=["Команды"], responses=PROTECTED_ERRORS)


@router.get("/get_groups", response_model=list[TeamResponse])
async def get_groups(
    course_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
):
    await course_access(conn, user, course_id)
    teams = await methods.get_teams_by_discipline(conn, course_id)
    return teams


@router.post(
    "/create_group", response_model=TeamResponse, status_code=status.HTTP_201_CREATED
)
async def create_group(
    data: TeamCreateRequest,
    user: AuthUser,
    conn: Connection,
):
    if not await check_is_teacher_or_admin(conn, user, data.discipline_id):
        raise HTTPException(
            status_code=403, detail="Только преподаватель курса может создавать команды"
        )
    return await methods.create_team(conn, data)


@router.get("/get_team_members", response_model=list[CourseMemberResponse])
async def get_team_members(
    team_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    team = await methods.get_team_by_id(conn, team_id)
    if team is None:
        raise HTTPException(404, "Команда не найдена")
    _, staff, member = await course_access(conn, user, team["discipline_id"])
    if not staff and (member is None or member.get("team_id") != team_id):
        raise HTTPException(
            403, "Список участников доступен своей команде и преподавателям курса"
        )
    members = await methods.get_team_members(conn, team_id)
    return members


@router.patch("/update_group", response_model=TeamResponse)
async def update_group(
    team_id: UUID = Query(...),
    data: TeamUpdateRequest = ...,
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    team = await methods.get_team_by_id(conn, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Команда не найдена")
    if not await check_is_teacher_or_admin(conn, user, team["discipline_id"]):
        raise HTTPException(
            status_code=403,
            detail="Только преподаватель курса может редактировать команды",
        )
    updated = await methods.update_team(conn, team_id, data)
    return updated


@router.delete("/delete_group", response_model=SuccessResponse)
async def delete_group(
    team_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    team = await methods.get_team_by_id(conn, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Команда не найдена")
    if not await check_is_teacher_or_admin(conn, user, team["discipline_id"]):
        raise HTTPException(
            status_code=403, detail="Только преподаватель курса может удалять команды"
        )
    deleted = await methods.delete_team(conn, team_id)
    return {"ok": True}
