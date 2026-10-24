"""Профиль текущего пользователя."""

from typing import Any

from fastapi import APIRouter

from backend.api.dependencies import CurrentUser
from backend.api.errors import PROTECTED_ERRORS
from backend.schemas.api import UserInfoResponse

router = APIRouter(tags=["Пользователи"], responses=PROTECTED_ERRORS)


@router.get("/get_user_info", response_model=UserInfoResponse)
async def get_user_info(user: CurrentUser) -> dict[str, Any]:
    return user
