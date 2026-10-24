"""Регистрация и вход; все обращения к БД проходят через db.methods."""

from typing import Any

import psycopg
from fastapi import APIRouter, HTTPException, status
from starlette.concurrency import run_in_threadpool

from backend.api.dependencies import Connection
from backend.api.security import hash_password, make_token, verify_password
from backend.db import methods
from backend.schemas.api import AuthRequest, AuthResponse, ErrorResponse, RegisterResponse
from backend.schemas.data import UserCreate, UserRegister

router = APIRouter(tags=["Пользователи"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse, "description": "Email уже зарегистрирован"}},
)
async def register(data: UserRegister, conn: Connection) -> dict[str, Any]:
    existing = await methods.get_user_by_email(conn, data.email, include_inactive=True)
    if existing:
        raise HTTPException(status_code=409, detail="Пользователь с такой почтой уже зарегистрирован")
    password_hash = await run_in_threadpool(hash_password, data.password)
    user = UserCreate(
        email=data.email, password_hash=password_hash,
        first_name=data.first_name, last_name=data.last_name,
    )
    try:
        return await methods.create_user(conn, user)
    except psycopg.errors.UniqueViolation as exc:
        raise HTTPException(status_code=409, detail="Пользователь с такой почтой уже зарегистрирован") from exc


@router.post(
    "/auth",
    response_model=AuthResponse,
    responses={401: {"model": ErrorResponse, "description": "Неверный email или пароль"}},
)
async def authenticate(data: AuthRequest, conn: Connection) -> dict[str, Any]:
    user = await methods.get_user_credentials(conn, data.email)
    if user is None or not await run_in_threadpool(verify_password, data.password, user["password_hash"]):
        raise HTTPException(
            status_code=401,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"access_token": make_token(user["id"]), "token_type": "bearer", "user_id": user["id"]}
