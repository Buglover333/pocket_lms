"""Password hashing and signed access tokens."""

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from fastapi import HTTPException

TOKEN_TTL = timedelta(hours=12)


def _secret_key() -> str:
    value = os.getenv("JWT_SECRET")
    if not value:
        raise HTTPException(status_code=503, detail="JWT_SECRET не настроен")
    return value


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    # Keep compatibility with accounts registered by the first API version.
    return f"scrypt$16384$8$1${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str | None) -> bool:
    try:
        algorithm, n, r, p, salt_text, digest_text = stored.split("$")
        if (algorithm, n, r, p) != ("scrypt", "16384", "8", "1"):
            return False
        salt = base64.urlsafe_b64decode(salt_text + "=" * (-len(salt_text) % 4))
        expected = base64.urlsafe_b64decode(digest_text + "=" * (-len(digest_text) % 4))
        digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(digest, expected)
    except (AttributeError, ValueError, TypeError):
        return False


def make_token(user_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + TOKEN_TTL},
        _secret_key(),
        algorithm="HS256",
    )


def token_user_id(token: str) -> UUID:
    try:
        payload = jwt.decode(
            token,
            _secret_key(),
            algorithms=["HS256"],
            options={"require": ["sub", "iat", "exp"]},
        )
        return UUID(payload["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Недействительный или просроченный токен",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
