"""Модули образовательной программы."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.dependencies import AuthUser, Connection, CurrentUser
from backend.api.errors import PROTECTED_ERRORS
from backend.db import methods
from backend.schemas.api import ModulesResponse
from backend.schemas.data import ModuleCreateRequest, ModuleResponse, ModuleUpdateRequest

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

    user_courses = await methods.get_user_disciplines(conn, user["id"], active_only=True)
    user_course_ids = {c["id"] for c in user_courses}

    has_access = is_curator or is_admin or any(d["id"] in user_course_ids for d in disciplines)
    if not has_access:
        raise HTTPException(status_code=403, detail="У вас нет доступа к этому модулю")

    filtered_disciplines = []
    for d in disciplines:
        d_copy = dict(d)
        is_teacher = (
            is_curator
            or is_admin
            or (d.get("author_id") == user["id"])
            or any(c["id"] == d["id"] and c.get("member_role") in ("owner", "teacher") for c in user_courses)
        )
        if not is_teacher:
            d_copy.pop("invite_code", None)
        filtered_disciplines.append(d_copy)

    return {"module": module, "disciplines": filtered_disciplines}


@router.post("/create_module", response_model=ModuleResponse, status_code=status.HTTP_201_CREATED)
async def create_module(
    data: ModuleCreateRequest,
    user: AuthUser,
    conn: Connection,
) -> dict[str, Any]:
    if data.curator_id != user["id"] and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Нельзя назначать другого куратора без прав администратора")
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
        raise HTTPException(status_code=403, detail="Только куратор модуля может редактировать модуль")
    updated = await methods.update_module(conn, module_id, data)
    return updated
