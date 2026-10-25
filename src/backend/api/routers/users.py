"""Профиль и настройки пользователя."""

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.api.dependencies import AuthUser, Connection, CurrentUser
from backend.api.errors import PROTECTED_ERRORS
from backend.db import methods
from backend.schemas.api import UserInfoResponse, ProfileSettingsUpdate
from backend.schemas.data import UserUpdate

router = APIRouter(tags=["Пользователи"], responses=PROTECTED_ERRORS)


@router.get("/get_user_info", response_model=UserInfoResponse)
async def get_user_info(user: CurrentUser) -> dict[str, Any]:
    return user


@router.patch("/update_settings", response_model=UserInfoResponse)
async def update_settings(data: ProfileSettingsUpdate, user: AuthUser, conn: Connection) -> dict[str, Any]:
    updated = await methods.update_user(conn, user["id"], UserUpdate(**data.model_dump(exclude_unset=True)))
    if updated is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return updated
