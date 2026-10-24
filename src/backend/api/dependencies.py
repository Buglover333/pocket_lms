"""Общие зависимости подключения и проверки текущего пользователя."""

from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

import psycopg
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.api.security import token_user_id
from backend.db import methods
from backend.db.connection import DatabaseConfigurationError, connection

async def get_connection() -> AsyncIterator[psycopg.AsyncConnection]:
    try:
        async with connection() as conn:
            yield conn
    except DatabaseConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except psycopg.OperationalError as exc:
        raise HTTPException(status_code=503, detail="База данных недоступна") from exc


Connection = Annotated[psycopg.AsyncConnection, Depends(get_connection)]
bearer = HTTPBearer(
    auto_error=False,
    description="Вставьте только access_token, без слова Bearer и без кавычек.",
)


async def require_token_user_id(
    user_id: UUID,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> UUID:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Требуется авторизация",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if token_user_id(credentials.credentials) != user_id:
        raise HTTPException(status_code=403, detail="Нельзя запрашивать данные другого пользователя")
    return user_id


async def require_current_user(
    user_id: Annotated[UUID, Depends(require_token_user_id)], conn: Connection,
) -> dict[str, Any]:
    user = await methods.get_user_by_id(conn, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user


CurrentUser = Annotated[dict[str, Any], Depends(require_current_user)]


async def require_auth_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    conn: Connection,
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Требуется авторизация",
            headers={"WWW-Authenticate": "Bearer"},
        )
    uid = token_user_id(credentials.credentials)
    user = await methods.get_user_by_id(conn, uid)
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user


AuthUser = Annotated[dict[str, Any], Depends(require_auth_user)]


async def check_is_teacher_or_admin(
    conn: psycopg.AsyncConnection,
    user: dict[str, Any],
    discipline_id: UUID | None = None,
) -> bool:
    """Проверяет, является ли пользователь преподавателем курса или администратором."""
    if user.get("is_admin"):
        return True
    if discipline_id is None:
        disciplines = await methods.get_user_disciplines(conn, user["id"], active_only=True)
        return any(d.get("member_role") in ("owner", "teacher") for d in disciplines)
    course = await methods.get_discipline_by_id(conn, discipline_id)
    if course and course.get("author_id") == user["id"]:
        return True
    members = await methods.get_discipline_members(conn, discipline_id)
    return any(
        m["user_id"] == user["id"]
        and m.get("role") in ("owner", "teacher")
        and m.get("status") == "active"
        for m in members
    )

