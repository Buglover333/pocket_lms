"""Модули образовательной программы."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.dependencies import AuthUser, Connection, CurrentUser
from backend.api.errors import PROTECTED_ERRORS
from backend.db import methods, invitations
from backend.schemas.api import ModulesResponse
from backend.schemas.identity import SuccessResponse
from backend.schemas.data import (
    ModuleCreateRequest,
    ModuleResponse,
    ModuleUpdateRequest,
)

router = APIRouter(tags=["Модули"], responses=PROTECTED_ERRORS)


@router.get("/get_modules", response_model=ModulesResponse)
async def get_modules(user: CurrentUser, conn: Connection) -> dict[str, Any]:
    return {"items": await methods.get_user_modules(conn, user["id"])}


@router.get("/get_module_data")
async def get_module_data(
    module_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    module = await methods.get_module_by_id(conn, module_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Модуль не найден")

    disciplines = await methods.get_disciplines_by_module(conn, module_id)
    is_curator = module.get("curator_id") == user["id"]
    is_admin = bool(user.get("is_admin"))

    user_courses = await methods.get_user_disciplines(
        conn, user["id"], active_only=True
    )
    user_course_ids = {c["id"] for c in user_courses}

    module_member = await invitations.module_member(conn, module_id, user["id"])
    module_teacher = await invitations.module_teacher(conn, module_id, user["id"])
    has_access = (
        is_curator
        or is_admin
        or module_member
        or any(d["id"] in user_course_ids for d in disciplines)
    )
    if not has_access:
        raise HTTPException(status_code=403, detail="У вас нет доступа к этому модулю")

    filtered_disciplines = []
    for d in disciplines:
        if (
            not (is_curator or is_admin or module_teacher)
            and d["id"] not in user_course_ids
        ):
            continue
        d_copy = dict(d)
        is_teacher = (
            is_curator
            or is_admin
            or (d.get("author_id") == user["id"])
            or any(
                c["id"] == d["id"] and c.get("member_role") in ("owner", "teacher")
                for c in user_courses
            )
        )
        if not is_teacher:
            d_copy.pop("invite_code", None)
        filtered_disciplines.append(d_copy)

    return {"module": module, "disciplines": filtered_disciplines}


@router.post(
    "/create_module", response_model=ModuleResponse, status_code=status.HTTP_201_CREATED
)
async def create_module(
    data: ModuleCreateRequest,
    user: AuthUser,
    conn: Connection,
) -> dict[str, Any]:
    if data.curator_id != user["id"] and not user.get("is_admin"):
        raise HTTPException(
            status_code=403,
            detail="Нельзя назначать другого куратора без прав администратора",
        )
    return await methods.create_module(conn, data)


@router.patch("/update_module", response_model=ModuleResponse)
async def update_module(
    module_id: UUID = Query(...),
    data: ModuleUpdateRequest = ...,
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    module = await methods.get_module_by_id(conn, module_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Модуль не найден")
    if module["curator_id"] != user["id"] and not user.get("is_admin"):
        raise HTTPException(
            status_code=403, detail="Только куратор модуля может редактировать модуль"
        )
    if (
        "curator_id" in data.model_fields_set
        and data.curator_id != module["curator_id"]
        and not user.get("is_admin")
    ):
        raise HTTPException(403, "Изменить создателя может только администратор")
    updated = await methods.update_module(conn, module_id, data)
    return updated


@router.delete("/remove_module_member", response_model=SuccessResponse)
async def remove_module_member(
    user: AuthUser,
    conn: Connection,
    module_id: UUID = Query(...),
    member_user_id: UUID = Query(...),
):
    from backend.db.identity import lock_user

    await lock_user(conn, member_user_id)
    module = await methods.get_module_by_id(conn, module_id)
    if module is None:
        raise HTTPException(404, "Модуль не найден")
    if not user.get("is_admin") and user["id"] != module["curator_id"]:
        raise HTTPException(403, "Исключать из модуля может только его создатель")
    courses = await methods.get_disciplines_by_module(conn, module_id)
    if not user.get("is_admin") and (
        member_user_id == module["curator_id"]
        or any(c["author_id"] == member_user_id for c in courses)
    ):
        raise HTTPException(
            403, "Нельзя снять права создателя; обратитесь к администратору"
        )
    await invitations.remove_module_member(conn, module_id, member_user_id, user["id"])
    return {"ok": True}
