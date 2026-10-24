"""Выдача будущей сборки frontend по действующему контракту POST /app."""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.schemas.api import ErrorResponse

PROJECT_ROOT = Path(__file__).resolve().parents[4]
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", str(PROJECT_ROOT / "frontend" / "dist")))
router = APIRouter(tags=["Приложение"])


@router.post(
    "/app", response_class=FileResponse,
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
