from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from psycopg.rows import dict_row
from starlette.concurrency import run_in_threadpool

from backend.api.security import hash_password, make_token, token_user_id, verify_password
from backend.schemas.api import (
    AuthRequest,
    AuthResponse,
    CoursesResponse,
    ErrorResponse,
    ModulesResponse,
    RegisterResponse,
    UserInfoResponse,
)
from backend.schemas.data import UserRegister

app = FastAPI(
    title="Pocket LMS API",
    version="0.2.0",
    responses={422: {"model": ErrorResponse, "description": "Неверный формат запроса"}},
)
bearer = HTTPBearer(
    auto_error=False,
    description="Вставьте только access_token, без слова Bearer и без кавычек.",
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", str(PROJECT_ROOT / "frontend" / "dist")))
if (FRONTEND_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    details = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        details.append(f"{location}: {error['msg']}")
    return JSONResponse(status_code=422, content={"detail": "; ".join(details)})


async def get_connection() -> AsyncIterator[psycopg.AsyncConnection]:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise HTTPException(status_code=503, detail="DATABASE_URL не настроен")
    try:
        async with await psycopg.AsyncConnection.connect(url, row_factory=dict_row) as conn:
            yield conn
    except psycopg.OperationalError as exc:
        raise HTTPException(status_code=503, detail="База данных недоступна") from exc


Connection = Annotated[psycopg.AsyncConnection, Depends(get_connection)]


async def require_current_user(
    user_id: UUID,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    conn: Connection,
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Требуется авторизация",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if token_user_id(credentials.credentials) != user_id:
        raise HTTPException(status_code=403, detail="Нельзя запрашивать данные другого пользователя")
    async with conn.cursor() as cur:
        await cur.execute(
            """SELECT id, email, first_name, last_name, middle_name, avatar_id,
                      is_admin, is_active, created_at, updated_at
               FROM users WHERE id = %s AND is_active = TRUE""",
            (user_id,),
        )
        user = await cur.fetchone()
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user


CurrentUser = Annotated[dict[str, Any], Depends(require_current_user)]
PROTECTED_ERRORS = {
    401: {"model": ErrorResponse, "description": "Требуется авторизация"},
    403: {"model": ErrorResponse, "description": "Запрошены данные другого пользователя"},
    404: {"model": ErrorResponse, "description": "Пользователь не найден"},
}


@app.post(
    "/app",
    response_class=FileResponse,
    tags=["Приложение"],
    responses={
        200: {"content": {"text/html": {}}, "description": "Собранный frontend"},
        503: {"model": ErrorResponse, "description": "Frontend ещё не собран"},
    },
)
async def frontend() -> FileResponse:
    index = FRONTEND_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=503, detail="Frontend приложения ещё не собран")
    return FileResponse(index, media_type="text/html")


@app.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Пользователи"],
    responses={409: {"model": ErrorResponse, "description": "Email уже зарегистрирован"}},
)
async def register(data: UserRegister, conn: Connection) -> dict[str, Any]:
    password_hash = await run_in_threadpool(hash_password, data.password)
    try:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1 FROM users WHERE lower(email) = %s", (data.email,))
            if await cur.fetchone():
                raise HTTPException(status_code=409, detail="Пользователь с такой почтой уже зарегистрирован")
            await cur.execute(
                """INSERT INTO users (email, password_hash, first_name, last_name)
                   VALUES (%s, %s, %s, %s)
                   RETURNING id, email, first_name, last_name, is_active, created_at""",
                (data.email, password_hash, data.first_name, data.last_name),
            )
            return await cur.fetchone()
    except psycopg.errors.UniqueViolation as exc:
        raise HTTPException(status_code=409, detail="Пользователь с такой почтой уже зарегистрирован") from exc


@app.post(
    "/auth",
    response_model=AuthResponse,
    tags=["Пользователи"],
    responses={401: {"model": ErrorResponse, "description": "Неверный email или пароль"}},
)
async def authenticate(data: AuthRequest, conn: Connection) -> dict[str, Any]:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT id, password_hash FROM users WHERE lower(email) = %s AND is_active = TRUE",
            (data.email,),
        )
        user = await cur.fetchone()
    if user is None or not await run_in_threadpool(verify_password, data.password, user["password_hash"]):
        raise HTTPException(
            status_code=401,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"access_token": make_token(user["id"]), "token_type": "bearer", "user_id": user["id"]}


@app.get("/get_courses", response_model=CoursesResponse, tags=["Курсы"], responses=PROTECTED_ERRORS)
async def get_courses(user: CurrentUser, conn: Connection) -> dict[str, Any]:
    async with conn.cursor() as cur:
        await cur.execute(
            """SELECT d.id, d.module_id, d.author_id, d.title, d.discipline_type,
                      d.status, d.description, d.cover_file_id, d.ends_at, dm.role, dm.team_id
               FROM discipline_members dm JOIN disciplines d ON d.id = dm.discipline_id
               WHERE dm.user_id = %s AND dm.status = 'active'
               ORDER BY dm.enrolled_at DESC, d.id""",
            (user["id"],),
        )
        return {"items": await cur.fetchall()}


@app.get("/get_modules", response_model=ModulesResponse, tags=["Модули"], responses=PROTECTED_ERRORS)
async def get_modules(user: CurrentUser, conn: Connection) -> dict[str, Any]:
    async with conn.cursor() as cur:
        await cur.execute(
            """SELECT DISTINCT m.id, m.title, m.description, m.curator_id
               FROM discipline_members dm
               JOIN disciplines d ON d.id = dm.discipline_id
               JOIN modules m ON m.id = d.module_id
               WHERE dm.user_id = %s AND dm.status = 'active'
               ORDER BY m.title, m.id""",
            (user["id"],),
        )
        return {"items": await cur.fetchall()}


@app.get("/get_user_info", response_model=UserInfoResponse, tags=["Пользователи"], responses=PROTECTED_ERRORS)
async def get_user_info(user: CurrentUser) -> dict[str, Any]:
    return user
