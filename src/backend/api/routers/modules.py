"""Модули активных курсов текущего пользователя."""

from typing import Any

from fastapi import APIRouter

from backend.api.dependencies import Connection, CurrentUser
from backend.api.errors import PROTECTED_ERRORS
from backend.db import methods
from backend.schemas.api import ModulesResponse

router = APIRouter(tags=["Модули"], responses=PROTECTED_ERRORS)


@router.get("/get_modules", response_model=ModulesResponse)
async def get_modules(user: CurrentUser, conn: Connection) -> dict[str, Any]:
    return {"items": await methods.get_user_modules(conn, user["id"])}
