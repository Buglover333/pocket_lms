"""Общие зависимости подключения и проверки текущего пользователя."""

from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

import psycopg
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.api.security import token_claims
from backend.db import identity
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

DEFAULT_MOCK_USER: dict[str, Any] = {
    "id": UUID("00000000-0000-0000-0000-000000000001"),
    "email": "developer@pocket-lms.local",
    "name": "Dev User",
    "role": "teacher",
    "is_admin": True,
    "is_active": True,
}


async def require_auth_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    conn: Connection,
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(
            401, "Требуется авторизация", headers={"WWW-Authenticate": "Bearer"}
        )
    uid, sid = token_claims(credentials.credentials)
    user = await methods.get_user_by_id(conn, uid)
    if user is None or not await identity.session_user(conn, sid, uid):
        raise HTTPException(
            401,
            "Сессия завершена. Войдите снова",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user["_session_id"] = sid
    return user


AuthUser = Annotated[dict[str, Any], Depends(require_auth_user)]

# Точка интеграции: зависимость для работы с файлами и общими роутами
get_current_user = require_auth_user


async def require_current_user(user_id: UUID, user: AuthUser) -> dict[str, Any]:
    if user_id != user["id"]:
        raise HTTPException(403, "Нельзя запрашивать данные другого пользователя")
    return user


CurrentUser = Annotated[dict[str, Any], Depends(require_current_user)]


async def check_is_teacher_or_admin(
    conn: psycopg.AsyncConnection,
    user: dict[str, Any],
    discipline_id: UUID | None = None,
) -> bool:
    """Проверяет, является ли пользователь преподавателем курса или администратором."""
    if user.get("is_admin"):
        return True
    if discipline_id is None:
        disciplines = await methods.get_user_disciplines(
            conn, user["id"], active_only=True
        )
        return any(d.get("member_role") in ("owner", "teacher") for d in disciplines)
    course = await methods.get_discipline_by_id(conn, discipline_id)
    if course and course.get("author_id") == user["id"]:
        return True
    if course and course.get("module_id"):
        module = await methods.get_module_by_id(conn, course["module_id"])
        if module and module["curator_id"] == user["id"]:
            return True
    members = await methods.get_discipline_members(conn, discipline_id)
    return any(
        m["user_id"] == user["id"]
        and m.get("role") in ("owner", "teacher")
        and m.get("status") == "active"
        for m in members
    )
