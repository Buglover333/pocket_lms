"""Test-only identities: explicit dependency overrides, never imported by application."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from backend.api.dependencies import bearer

DEFAULT_MOCK_USER = {
    "id": UUID("00000000-0000-0000-0000-000000000001"),
    "email": "developer@pocket-lms.local",
    "name": "Dev User",
    "role": "teacher",
    "is_admin": True,
    "is_active": True,
}


async def isolated_user_dependency(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
):
    if credentials is None or credentials.credentials != "dev-token":
        raise HTTPException(
            401, "Требуется авторизация", headers={"WWW-Authenticate": "Bearer"}
        )
    return DEFAULT_MOCK_USER.copy()
