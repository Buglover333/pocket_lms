"""Единый формат ошибок API и описание ошибок защищённых запросов."""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.schemas.api import ErrorResponse

PROTECTED_ERRORS = {
    401: {"model": ErrorResponse, "description": "Требуется авторизация"},
    403: {"model": ErrorResponse, "description": "Запрошены данные другого пользователя"},
    404: {"model": ErrorResponse, "description": "Пользователь не найден"},
}


async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    details = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        details.append(f"{location}: {error['msg']}")
    return JSONResponse(status_code=422, content={"detail": "; ".join(details)})
