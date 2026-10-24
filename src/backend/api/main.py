"""Точка сборки приложения: общие настройки и подключение роутеров."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from backend.api.errors import validation_error
from backend.api.routers import auth, courses, frontend, modules, users
from backend.schemas.api import ErrorResponse

app = FastAPI(
    title="Pocket LMS API",
    version="0.3.0",
    responses={422: {"model": ErrorResponse, "description": "Неверный формат запроса"}},
)
app.add_exception_handler(RequestValidationError, validation_error)

for router in (auth.router, users.router, courses.router, modules.router, frontend.router):
    app.include_router(router)

if (frontend.FRONTEND_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=frontend.FRONTEND_DIR / "assets"), name="assets")
