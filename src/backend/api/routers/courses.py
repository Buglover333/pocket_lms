"""Курсы и дисциплины."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.dependencies import AuthUser, Connection, CurrentUser, check_is_teacher_or_admin
from backend.api.errors import PROTECTED_ERRORS
from backend.api.access import course_access
from backend.db import methods
from backend.schemas.api import CoursesResponse
from backend.schemas.data import (
    DisciplineCreateRequest,
    DisciplineMemberCreateRequest,
    DisciplineMemberProfileResponse,
    DisciplineMemberResponse,
    DisciplineResponse,
    DisciplineUpdateRequest,
)

router = APIRouter(tags=["Курсы"], responses=PROTECTED_ERRORS)


@router.get("/get_courses", response_model=CoursesResponse)
async def get_courses(user: CurrentUser, conn: Connection) -> dict[str, Any]:
    return {"items": await methods.get_user_disciplines(conn, user["id"], active_only=True)}


@router.get("/get_course_data")
async def get_course_data(
    course_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    course, is_teacher, _ = await course_access(conn, user, course_id)

    course_data = dict(course)
    if not is_teacher and not user.get("is_admin"):
        course_data.pop("invite_code", None)

    lessons = await methods.get_lessons_by_discipline(conn, course_id)
    return {"course": course_data, "lessons": lessons if is_teacher else [x for x in lessons if x["is_published"]]}


@router.post("/create_course", response_model=DisciplineResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    data: DisciplineCreateRequest,
    user: AuthUser,
    conn: Connection,
) -> dict[str, Any]:
    if data.author_id != user["id"] and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Нельзя создавать курс от имени другого автора")
    return await methods.create_discipline(conn, data)


@router.patch("/update_course", response_model=DisciplineResponse)
async def update_course(
    course_id: UUID = Query(...),
    data: DisciplineUpdateRequest = ...,
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    course = await methods.get_discipline_by_id(conn, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Курс не найден")
    if not await check_is_teacher_or_admin(conn, user, course_id):
        raise HTTPException(status_code=403, detail="Только преподаватель курса может редактировать курс")
    updated = await methods.update_discipline(conn, course_id, data)
    return updated


@router.post("/create_invitation")
async def create_invitation(
    course_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    course = await methods.get_discipline_by_id(conn, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Курс не найден")
    if not await check_is_teacher_or_admin(conn, user, course_id):
        raise HTTPException(status_code=403, detail="Только преподаватель курса может создавать приглашения")
    return {
        "course_id": course["id"],
        "invite_code": course["invite_code"],
        "invitation_url": f"/courses/join?code={course['invite_code']}",
    }


@router.post("/accept_invitation", response_model=DisciplineMemberResponse)
async def accept_invitation(
    invite_code: str = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    course = await methods.get_discipline_by_invite_code(conn, invite_code)
    if course is None:
        raise HTTPException(status_code=404, detail="Неверный код приглашения")
    member_data = DisciplineMemberCreateRequest(
        discipline_id=course["id"],
        user_id=user["id"],
        role="student",
        status="active",
    )
    return await methods.add_discipline_member(conn, member_data)


@router.get("/get_members")
async def get_members(
    course_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    course = await methods.get_discipline_by_id(conn, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Курс не найден")
    is_teacher = await check_is_teacher_or_admin(conn, user, course_id)
    members = await methods.get_discipline_members(conn, course_id)
    is_member = any(m["user_id"] == user["id"] and m.get("status") == "active" for m in members)
    if not (is_teacher or is_member or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="Вы не являетесь участником этого курса")
    profiles = await methods.get_discipline_members_with_profiles(conn, course_id)
    return {"items": profiles}
