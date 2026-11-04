"""Курсы и дисциплины."""

import secrets
from typing import Any
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.access import course_access
from backend.api.dependencies import (
    AuthUser,
    Connection,
    CurrentUser,
    check_is_teacher_or_admin,
)
from backend.api.errors import PROTECTED_ERRORS
from backend.api.security import secret_digest
from backend.db import invitations, methods
from backend.schemas.api import (
    CourseCreatedResponse,
    CourseCreateRequest,
    CourseItem,
    CourseMemberResponse,
)
from backend.schemas.data import (
    DisciplineCreateRequest,
    DisciplineResponse,
    DisciplineUpdateRequest,
)
from backend.schemas.identity import (
    InvitationAcceptance,
    InvitationCreate,
    InvitationResponse,
    SuccessResponse,
)

router = APIRouter(tags=["Курсы"], responses=PROTECTED_ERRORS)


@router.get("/get_courses", response_model=list[CourseItem])
async def get_courses(user: CurrentUser, conn: Connection) -> list[dict[str, Any]]:
    return await methods.get_user_disciplines(conn, user["id"], active_only=True)


@router.get("/get_course_data", response_model=DisciplineResponse)
async def get_course_data(
    course_id: UUID = Query(...), user: AuthUser = None, conn: Connection = None
):
    course, _, _ = await course_access(conn, user, course_id)
    return course


@router.post(
    "/create_course",
    response_model=CourseCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_course(
    data: CourseCreateRequest,
    user: AuthUser,
    conn: Connection,
) -> dict[str, Any]:
    if data.author_id != user["id"] and not user.get("is_admin"):
        raise HTTPException(
            status_code=403, detail="Нельзя создавать курс от имени другого автора"
        )
    if data.module_id:
        module = await methods.get_module_by_id(conn, data.module_id)
        if module is None:
            raise HTTPException(404, "Модуль не найден")
        if not user.get("is_admin") and module["curator_id"] != user["id"]:
            raise HTTPException(
                403, "Добавлять курс в модуль может только создатель модуля"
            )
    import psycopg

    try:
        return await methods.create_discipline(
            conn, DisciplineCreateRequest(**data.model_dump())
        )
    except psycopg.errors.UniqueViolation as exc:
        raise HTTPException(
            409, "Код курса уже существует; используйте другой или не указывайте его"
        ) from exc


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
        raise HTTPException(
            status_code=403,
            detail="Только преподаватель курса может редактировать курс",
        )
    updated = await methods.update_discipline(conn, course_id, data)
    return updated


async def can_invite(conn, user, course):
    if user.get("is_admin"):
        return True
    if course.get("module_id"):
        return await invitations.module_teacher(conn, course["module_id"], user["id"])
    return await check_is_teacher_or_admin(conn, user, course["id"])


@router.post("/create_invitation", response_model=InvitationResponse, status_code=201)
async def create_invitation(data: InvitationCreate, user: AuthUser, conn: Connection):
    ids = data.course_ids if data.module_id else [data.course_id]
    if data.module_id:
        module = await methods.get_module_by_id(conn, data.module_id)
        if module is None:
            raise HTTPException(404, "Модуль не найден")
        if not user.get("is_admin") and not await invitations.module_teacher(
            conn, data.module_id, user["id"]
        ):
            raise HTTPException(
                403,
                "Приглашать может преподаватель курса внутри модуля или создатель модуля",
            )
    for cid in ids:
        course = await methods.get_discipline_by_id(conn, cid)
        if course is None:
            raise HTTPException(404, "Курс не найден")
        if data.module_id and course["module_id"] != data.module_id:
            raise HTTPException(
                422, "Все выбранные курсы должны находиться в указанном модуле"
            )
        if not await can_invite(conn, user, course):
            raise HTTPException(403, "Нет права приглашать в этот курс")
    raw = secrets.token_urlsafe(24)
    row = await invitations.create(
        conn,
        user["id"],
        secret_digest(raw),
        data.module_id,
        ids,
        data.role,
        data.expires_in_days,
        data.max_uses,
    )
    return {
        **row,
        "course_ids": ids,
        "invite_code": raw,
        "invitation_url": "/join?code=" + quote(raw),
    }


@router.post("/accept_invitation", response_model=InvitationAcceptance)
async def accept_invitation(
    user: AuthUser,
    conn: Connection,
    invite_code: str = Query(..., min_length=1, max_length=128),
):
    from backend.api.routers.auth import throttle

    await throttle("invite:" + str(user["id"]), 100)
    # Lock user before invitation, also used by exclusion to serialize membership changes.
    from backend.db.identity import lock_user

    await lock_user(conn, user["id"])
    result, error = await invitations.accept(
        conn, secret_digest(invite_code), user["id"]
    )
    if error:
        raise HTTPException(
            409 if error == "full" else 404,
            "Приглашение недействительно, отозвано или исчерпано",
        )
    return result


@router.delete("/revoke_invitation", response_model=SuccessResponse)
async def revoke_invitation(
    user: AuthUser, conn: Connection, invitation_id: UUID = Query(...)
):
    inv = await invitations.get(conn, invitation_id)
    if inv is None:
        raise HTTPException(404, "Приглашение не найдено")
    ids = await invitations.course_ids(conn, invitation_id)
    for cid in ids:
        course = await methods.get_discipline_by_id(conn, cid)
        if not await can_invite(conn, user, course):
            raise HTTPException(403, "Нет права отозвать приглашение")
    await invitations.revoke(conn, invitation_id, user["id"])
    return {"ok": True}


@router.delete("/remove_course_member", response_model=SuccessResponse)
async def remove_course_member(
    user: AuthUser,
    conn: Connection,
    course_id: UUID = Query(...),
    member_user_id: UUID = Query(...),
):
    from backend.db.identity import lock_user

    await lock_user(conn, member_user_id)
    course = await methods.get_discipline_by_id(conn, course_id)
    if course is None:
        raise HTTPException(404, "Курс не найден")
    module = (
        await methods.get_module_by_id(conn, course["module_id"])
        if course["module_id"]
        else None
    )
    creator = module["curator_id"] if module else course["author_id"]
    if not user.get("is_admin") and member_user_id in {creator, course["author_id"]}:
        raise HTTPException(403, "Права создателя может изменить только администратор")
    members = await methods.get_discipline_members(conn, course_id)
    member = next(
        (
            m
            for m in members
            if m["user_id"] == member_user_id and m["status"] == "active"
        ),
        None,
    )
    if member is None:
        raise HTTPException(404, "Активный участник не найден")
    allowed = user.get("is_admin") or user["id"] == creator
    if member["role"] == "student":
        allowed = allowed or await check_is_teacher_or_admin(conn, user, course_id)
    if not allowed:
        raise HTTPException(403, "Снять права преподавателя может только создатель")
    await invitations.remove_course_member(conn, course_id, member_user_id, user["id"])
    return {"ok": True}


@router.get("/get_members", response_model=list[CourseMemberResponse])
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
    is_member = any(
        m["user_id"] == user["id"] and m.get("status") == "active" for m in members
    )
    if not (is_teacher or is_member or user.get("is_admin")):
        raise HTTPException(
            status_code=403, detail="Вы не являетесь участником этого курса"
        )
    profiles = await methods.get_discipline_members_with_profiles(conn, course_id)
    return profiles
