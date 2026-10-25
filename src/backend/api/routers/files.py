"""Файлы и материалы."""

from typing import Any
from asyncio import to_thread
from uuid import uuid4
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.dependencies import AuthUser, Connection
from backend.api.errors import PROTECTED_ERRORS
from backend.api.access import file_access, material_access, submission_access
from backend.schemas.api import FileUploadRequest, FileUploadResponse, FileDownloadResponse
from backend.services import storage
from backend.db import methods
from backend.schemas.data import FileCreateRequest, FileResponse

router = APIRouter(tags=["Файлы"], responses=PROTECTED_ERRORS)


@router.post("/upload_file", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    data: FileCreateRequest,
    user: AuthUser,
    conn: Connection,
) -> dict[str, Any]:
    if data.uploader_id and data.uploader_id != user["id"]:
        raise HTTPException(403, "Нельзя загрузить файл от чужого имени")
    if data.url.startswith("s3:") or (data.meta and any(k in data.meta for k in ("storage", "bucket", "key", "upload_status"))):
        raise HTTPException(422, "Для S3 используйте /create_file_upload")
    if not data.url.startswith(("https://", "http://")):
        raise HTTPException(422, "Ожидается внешняя HTTP-ссылка")
    await attachment_write_access(conn, user, data.lesson_id, data.submission_id)
    data = data.model_copy(update={"uploader_id": user["id"]})
    return await methods.create_file(conn, data)


@router.get("/get_file", response_model=FileResponse)
async def get_file(
    file_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    return await file_access(conn, user, file_id)


@router.delete("/delete_file")
async def delete_file(
    file_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    await file_access(conn, user, file_id, write=True)
    await methods.delete_file(conn, file_id)
    return {"ok": True}


async def attachment_write_access(conn, user, lesson_id, submission_id):
    if lesson_id and submission_id:
        raise HTTPException(422, "Файл может относиться только к одному объекту")
    if lesson_id:
        _, staff = await material_access(conn, user, lesson_id)
        if not staff:
            raise HTTPException(403, "Только преподаватель может прикреплять материал")
    if submission_id:
        submission, _, _ = await submission_access(conn, user, submission_id)
        if submission["submitted_by"] != user["id"] or submission["status"] not in ("draft", "returned"):
            if not user.get("is_admin"):
                raise HTTPException(403, "Файлы можно прикреплять к своему черновику или возвращённой работе")


@router.post("/create_file_upload", status_code=201, response_model=FileUploadResponse)
async def create_file_upload(data: FileUploadRequest, user: AuthUser, conn: Connection):
    await attachment_write_access(conn, user, data.lesson_id, data.submission_id)
    key = f"uploads/{user['id']}/{uuid4().hex}"
    bucket, signed = await to_thread(storage.upload_url, key, data.mime_type)
    record = await methods.create_file(conn, FileCreateRequest(
        **data.model_dump(), uploader_id=user["id"], url=f"s3://{bucket}/{key}",
        meta={"storage": "s3", "bucket": bucket, "key": key, "upload_status": "pending"}))
    return {"file_id": record["id"], "upload_url": signed["url"],
            "fields": signed["fields"], "expires_in": storage.TTL}


@router.post("/complete_file_upload", response_model=FileResponse)
async def complete_file_upload(file_id: UUID, user: AuthUser, conn: Connection):
    record = await file_access(conn, user, file_id, write=True)
    if record.get("uploader_id") != user["id"]:
        raise HTTPException(403, "Подтвердить загрузку может только отправитель")
    meta = record.get("meta") or {}
    if meta.get("storage") != "s3":
        raise HTTPException(422, "Это не загрузка S3")
    await to_thread(storage.verify_upload, meta["bucket"], meta["key"], record["size_bytes"], record["mime_type"])
    return await methods.complete_file_upload(conn, file_id)


@router.get("/get_file_download", response_model=FileDownloadResponse)
async def get_file_download(file_id: UUID, user: AuthUser, conn: Connection):
    record = await file_access(conn, user, file_id)
    meta = record.get("meta") or {}
    if meta.get("storage") != "s3":
        return {"download_url": record["url"], "expires_in": None}
    if meta.get("upload_status") != "ready":
        raise HTTPException(409, "Загрузка файла ещё не подтверждена")
    url = await to_thread(storage.download_url, meta["bucket"], meta["key"])
    return {"download_url": url, "expires_in": storage.TTL}
