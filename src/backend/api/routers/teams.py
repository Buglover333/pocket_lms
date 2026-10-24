"""Команды и группы обучающихся."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.dependencies import AuthUser, Connection, check_is_teacher_or_admin
from backend.api.errors import PROTECTED_ERRORS
from backend.db import methods
from backend.schemas.data import TeamCreateRequest, TeamResponse, TeamUpdateRequest

router = APIRouter(tags=["Команды"], responses=PROTECTED_ERRORS)


@router.get("/get_groups")
async def get_groups(
    course_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    teams = await methods.get_teams_by_discipline(conn, course_id)
    return {"items": teams}


@router.post("/create_group", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    data: TeamCreateRequest,
    user: AuthUser,
    conn: Connection,
) -> dict[str, Any]:
    if not await check_is_teacher_or_admin(conn, user, data.discipline_id):
        raise HTTPException(status_code=403, detail="Только преподаватель курса может создавать команды")
    return await methods.create_team(conn, data)


@router.get("/get_team_members")
async def get_team_members(
    team_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    members = await methods.get_team_members(conn, team_id)
    return {"items": members}


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
        raise HTTPException(status_code=403, detail="Только преподаватель курса может редактировать команды")
    updated = await methods.update_team(conn, team_id, data)
    return updated


@router.delete("/delete_group")
async def delete_group(
    team_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    team = await methods.get_team_by_id(conn, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Команда не найдена")
    if not await check_is_teacher_or_admin(conn, user, team["discipline_id"]):
        raise HTTPException(status_code=403, detail="Только преподаватель курса может удалять команды")
    deleted = await methods.delete_team(conn, team_id)
    return {"ok": True}
