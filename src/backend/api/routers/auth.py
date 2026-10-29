"""Регистрация и вход; все обращения к БД проходят через db.methods."""

import os
import secrets
from typing import Annotated, Any, Literal
from uuid import UUID

import psycopg
from fastapi import (
    APIRouter,
    Cookie,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from starlette.concurrency import run_in_threadpool

from backend.api.dependencies import AuthUser, Connection
from backend.api.security import (
    ensure_token_configuration,
    hash_password,
    make_token,
    secret_digest,
    verify_password,
)
from backend.db import identity, methods
from backend.schemas.api import (
    AuthRequest,
    AuthResponse,
    ErrorResponse,
    RegisterResponse,
)
from backend.schemas.data import UserCreate, UserRegister
from backend.schemas.identity import (
    AccountStatusResponse,
    BlockAccount,
    ChangePassword,
    MessageResponse,
    ResetCodeResponse,
    ResetPassword,
    SessionList,
    SuccessResponse,
)

router = APIRouter(
    tags=["Пользователи"],
    responses={
        401: {
            "model": ErrorResponse,
            "description": "Неверные учётные данные или завершённая сессия",
        },
        403: {"model": ErrorResponse, "description": "Недостаточно прав"},
        429: {"model": ErrorResponse, "description": "Превышен лимит попыток"},
    },
)


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"model": ErrorResponse, "description": "Email уже зарегистрирован"}
    },
)
async def register(
    data: UserRegister, conn: Connection, request: Request
) -> dict[str, Any]:
    await throttle("register:" + client_key(request), 20)
    existing = await methods.get_user_by_email(conn, data.email, include_inactive=True)
    if existing:
        raise HTTPException(
            status_code=409, detail="Пользователь с такой почтой уже зарегистрирован"
        )
    password_hash = await run_in_threadpool(hash_password, data.password)
    user = UserCreate(
        email=data.email,
        password_hash=password_hash,
        first_name=data.first_name,
        last_name=data.last_name,
    )
    try:
        return await methods.create_user(conn, user)
    except psycopg.errors.UniqueViolation as exc:
        raise HTTPException(
            status_code=409, detail="Пользователь с такой почтой уже зарегистрирован"
        ) from exc


@router.post(
    "/auth",
    response_model=AuthResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Неверный email или пароль"}
    },
)
async def authenticate(
    data: AuthRequest,
    conn: Connection,
    request: Request,
    response: Response,
    device_name: str = Query(default="Устройство", min_length=1, max_length=100),
) -> dict[str, Any]:
    # A login creates one independent device session. Refresh tokens stay in HttpOnly cookies.
    ensure_token_configuration()
    await throttle("login-email:" + data.email, 10)
    await throttle("login-ip:" + client_key(request), 100)
    user = await identity.credentials_for_update(conn, data.email)
    # Perform an equally expensive password hash check for unknown accounts.
    stored = user["password_hash"] if user and user["password_hash"] else DUMMY_HASH
    valid = await run_in_threadpool(verify_password, data.password, stored)
    if user is None or not valid:
        raise HTTPException(
            401, "Неверный email или пароль", headers={"WWW-Authenticate": "Bearer"}
        )
    raw = secrets.token_urlsafe(32)
    session = await identity.create_session(
        conn, user["id"], secret_digest(raw), device_name
    )
    set_refresh_cookie(response, raw)
    await identity.event(conn, user["id"], "login", session["id"])
    return token_response(session)


DUMMY_HASH = hash_password(secrets.token_urlsafe(32))
COOKIE = "pocket_lms_refresh"


def client_key(request):
    # Never trust arbitrary X-Forwarded-For. Configure trusted proxy forwarding at the server.
    return request.client.host if request.client else "unknown"


async def throttle(key, limit):
    if not await identity.rate_limit(secret_digest(key), limit):
        raise HTTPException(
            429,
            "Слишком много попыток. Повторите через 15 минут",
            headers={"Retry-After": "900"},
        )


def set_refresh_cookie(response, raw):
    response.set_cookie(
        COOKIE,
        raw,
        max_age=90 * 24 * 3600,
        httponly=True,
        secure=os.getenv("AUTH_COOKIE_SECURE", "true").lower() != "false",
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


def token_response(session):
    return {
        "access_token": make_token(session["user_id"], session["id"]),
        "token_type": "bearer",
        "user_id": session["user_id"],
        "session_id": session["id"],
        "expires_in": 900,
    }


@router.post(
    "/auth/refresh",
    response_model=AuthResponse,
    summary="Обновить вход на текущем устройстве",
    description="Отправьте cookie, установленную при входе, и X-Requested-With: PocketLMS. Токен обновления одноразовый; повторное использование завершает сессию этого устройства. Клиент должен выполнять обновления последовательно.",
)
async def refresh(
    request: Request,
    response: Response,
    x_requested_with: Annotated[
        Literal["PocketLMS"],
        Header(description="Защита от CSRF", examples=["PocketLMS"]),
    ],
    refresh_token: Annotated[str | None, Cookie(alias=COOKIE)] = None,
):
    # Custom header cannot be sent by a cross-site HTML form; API has no permissive CORS.
    ensure_token_configuration()
    await throttle("refresh:" + client_key(request), 100)
    raw = refresh_token
    if not raw:
        raise HTTPException(401, "Сессия отсутствует. Войдите снова")
    new_raw = secrets.token_urlsafe(32)
    session = await identity.rotate_refresh(secret_digest(raw), secret_digest(new_raw))
    if not session:
        raise HTTPException(401, "Сессия завершена. Войдите снова")
    set_refresh_cookie(response, new_raw)
    return token_response(session)


@router.post(
    "/auth/logout",
    response_model=SuccessResponse,
    summary="Выйти на текущем устройстве",
)
async def logout(user: AuthUser, conn: Connection, response: Response):
    await identity.revoke_session(conn, user["_session_id"], user["id"])
    response.delete_cookie(COOKIE, path="/")
    response.headers["Cache-Control"] = "no-store"
    return {"ok": True}


@router.get(
    "/auth/sessions",
    response_model=SessionList,
    summary="Посмотреть свои активные устройства",
)
async def list_sessions(user: AuthUser, conn: Connection):
    rows = await identity.sessions(conn, user["id"])
    return {
        "items": [dict(row, current=row["id"] == user["_session_id"]) for row in rows]
    }


@router.post(
    "/auth/change_password",
    response_model=MessageResponse,
    summary="Сменить пароль",
    description="Требуется текущий пароль. Завершает все сессии, включая текущую; затем нужно войти снова.",
)
async def change_password(
    data: ChangePassword, user: AuthUser, conn: Connection, response: Response
):
    await throttle("password-change:" + str(user["id"]), 10)
    credentials = await identity.credentials_for_update(conn, user["email"])
    if not credentials or not await run_in_threadpool(
        verify_password, data.current_password, credentials["password_hash"]
    ):
        raise HTTPException(401, "Неверный текущий пароль")
    digest = await run_in_threadpool(hash_password, data.password)
    await identity.replace_password(conn, user["id"], digest)
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True, "detail": "Пароль изменён. Войдите снова на своих устройствах"}


@router.post(
    "/admin/password_reset",
    response_model=ResetCodeResponse,
    summary="Выдать одноразовый код восстановления",
    description="Только разработчик-администратор после ручной проверки личности. Без внешнего почтового сервиса. Код показывается один раз, действует 30 минут; передайте его пользователю по проверенному личному каналу.",
)
async def issue_password_reset(
    user: AuthUser, conn: Connection, response: Response, user_id: UUID = Query(...)
):
    if not user.get("is_admin"):
        raise HTTPException(403, "Только администратор может выдать код восстановления")
    raw = secrets.token_urlsafe(32)
    result = await identity.issue_reset(conn, user_id, secret_digest(raw), user["id"])
    if result is None:
        raise HTTPException(404, "Активный пользователь не найден")
    response.headers["Cache-Control"] = "no-store"
    return {"reset_code": raw, "expires_at": result["expires_at"]}


@router.post(
    "/auth/reset_password",
    response_model=MessageResponse,
    summary="Восстановить пароль по коду администратора",
)
async def reset_password(
    data: ResetPassword, conn: Connection, request: Request, response: Response
):
    await throttle("reset:" + client_key(request), 10)
    digest = await run_in_threadpool(hash_password, data.password)
    if not await identity.reset_password(conn, secret_digest(data.reset_code), digest):
        raise HTTPException(400, "Код недействителен или срок его действия истёк")
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True, "detail": "Пароль восстановлен. Войдите снова"}


@router.patch(
    "/admin/account_status",
    response_model=AccountStatusResponse,
    summary="Заблокировать или разблокировать аккаунт",
)
async def account_status(
    data: BlockAccount, user: AuthUser, conn: Connection, user_id: UUID = Query(...)
):
    if not user.get("is_admin"):
        raise HTTPException(403, "Только администратор может блокировать аккаунт")
    if user_id == user["id"]:
        raise HTTPException(
            409, "Нельзя заблокировать собственный аккаунт администратора"
        )
    result = await identity.set_blocked(conn, user_id, data.blocked, user["id"])
    if result is None:
        raise HTTPException(404, "Пользователь не найден")
    return result
