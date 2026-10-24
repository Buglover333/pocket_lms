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
    return {"module": module, "disciplines": disciplines}


@router.post("/create_module", response_model=ModuleResponse, status_code=status.HTTP_201_CREATED)
async def create_module(
    data: ModuleCreateRequest,
    user: AuthUser,
    conn: Connection,
) -> dict[str, Any]:
    return await methods.create_module(conn, data)


@router.patch("/update_module", response_model=ModuleResponse)
async def update_module(
    module_id: UUID = Query(...),
    data: ModuleUpdateRequest = None,
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    updated = await methods.update_module(conn, module_id, data)
    if updated is None:
        raise HTTPException(status_code=404, detail="Модуль не найден")
    return updated
