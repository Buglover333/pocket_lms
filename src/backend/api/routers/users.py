"""Профиль и настройки пользователя."""

from typing import Any

from fastapi import APIRouter, HTTPException, Response
from starlette.concurrency import run_in_threadpool

from backend.api.dependencies import AuthUser, Connection, CurrentUser
from backend.api.errors import PROTECTED_ERRORS
from backend.api.routers.auth import COOKIE, throttle
from backend.api.security import verify_password
from backend.db import identity, methods
from backend.schemas.api import (
    DeleteAccountRequest,
    ProfileSettingsUpdate,
    UserInfoResponse,
)
from backend.schemas.data import UserUpdate
from backend.schemas.identity import SuccessResponse

router = APIRouter(tags=["Пользователи"], responses=PROTECTED_ERRORS)


@router.get("/get_user_info", response_model=UserInfoResponse)
async def get_user_info(user: CurrentUser) -> dict[str, Any]:
    return user


@router.patch("/update_settings", response_model=UserInfoResponse)
async def update_settings(
    data: ProfileSettingsUpdate, user: AuthUser, conn: Connection
) -> dict[str, Any]:
    if data.avatar_id is not None:
        avatar = await methods.get_file_by_id(conn, data.avatar_id)
        if avatar is None:
            raise HTTPException(404, "Файл аватара не найден")
        if (
            avatar.get("uploader_id") != user["id"]
            or avatar.get("lesson_id")
            or avatar.get("submission_id")
        ):
            raise HTTPException(
                403,
                "Выберите собственный файл изображения без привязки к материалу или работе",
            )
        if avatar.get("file_type") != "image":
            raise HTTPException(422, "Аватар должен быть изображением")
        if (avatar.get("meta") or {}).get("storage") == "s3" and (
            avatar.get("meta") or {}
        ).get("upload_status") != "ready":
            raise HTTPException(409, "Сначала завершите загрузку аватара")
    updated = await methods.update_user(
        conn, user["id"], UserUpdate(**data.model_dump(exclude_unset=True))
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return updated


@router.delete(
    "/delete_account",
    response_model=SuccessResponse,
    summary="Деактивировать свой аккаунт",
)
async def delete_account(
    data: DeleteAccountRequest, user: AuthUser, conn: Connection, response: Response
):
    if user.get("is_admin"):
        raise HTTPException(403, "Аккаунт администратора отключается разработчиками")
    await throttle("delete-account:" + str(user["id"]), 10)
    credentials = await identity.credentials_for_update(conn, user["email"])
    if not credentials or not await run_in_threadpool(
        verify_password, data.current_password, credentials["password_hash"]
    ):
        raise HTTPException(401, "Неверный текущий пароль")
    await identity.set_blocked(conn, user["id"], True, user["id"])
    await identity.event(conn, user["id"], "account_deactivated", user["id"])
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}
