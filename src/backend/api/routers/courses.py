"""Курсы текущего пользователя."""

from typing import Any

from fastapi import APIRouter

from backend.api.dependencies import Connection, CurrentUser
from backend.api.errors import PROTECTED_ERRORS
from backend.db import methods
from backend.schemas.api import CoursesResponse

router = APIRouter(tags=["Курсы"], responses=PROTECTED_ERRORS)


@router.get("/get_courses", response_model=CoursesResponse)
async def get_courses(user: CurrentUser, conn: Connection) -> dict[str, Any]:
    return {"items": await methods.get_user_disciplines(conn, user["id"], active_only=True)}
