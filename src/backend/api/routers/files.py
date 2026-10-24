"""Файлы и материалы."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.dependencies import AuthUser, Connection
from backend.api.errors import PROTECTED_ERRORS
from backend.db import methods
from backend.schemas.data import FileCreateRequest, FileResponse

router = APIRouter(tags=["Файлы"], responses=PROTECTED_ERRORS)


@router.post("/upload_file", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    data: FileCreateRequest,
    user: AuthUser,
    conn: Connection,
) -> dict[str, Any]:
    if data.uploader_id and data.uploader_id != user["id"] and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Нельзя загрузить файл от чужого имени")
    if not data.uploader_id:
        data = data.model_copy(update={"uploader_id": user["id"]})
    return await methods.create_file(conn, data)


@router.get("/get_file", response_model=FileResponse)
async def get_file(
    file_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    file_record = await methods.get_file_by_id(conn, file_id)
    if file_record is None:
        raise HTTPException(status_code=404, detail="Файл не найден")
    return file_record


@router.delete("/delete_file")
async def delete_file(
    file_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    file_record = await methods.get_file_by_id(conn, file_id)
    if file_record is None:
        raise HTTPException(status_code=404, detail="Файл не найден")
    if file_record.get("uploader_id") and file_record["uploader_id"] != user["id"] and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Нельзя удалить чужой файл")
    deleted = await methods.delete_file(conn, file_id)
    return {"ok": True}
