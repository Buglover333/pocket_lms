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
