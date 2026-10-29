"""Точка сборки приложения: общие настройки и подключение роутеров."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from backend.api.errors import validation_error
from backend.api.routers import (
    assignments,
    auth,
    courses,
    files,
    frontend,
    lessons,
    modules,
    submissions,
    teams,
    users,
)
from backend.schemas.api import ErrorResponse

app = FastAPI(
    title="Pocket LMS API",
    version="0.5.0",
    responses={422: {"model": ErrorResponse, "description": "Неверный формат запроса"}},
)
app.add_exception_handler(RequestValidationError, validation_error)

for router in (
    auth.router,
    users.router,
    courses.router,
    modules.router,
    lessons.router,
    assignments.router,
    submissions.router,
    teams.router,
    files.router,
    frontend.router,
):
    app.include_router(router)

if (frontend.FRONTEND_DIR / "assets").is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=frontend.FRONTEND_DIR / "assets"),
        name="assets",
    )


@app.middleware("http")
async def prevent_private_response_caching(request, call_next):
    response = await call_next(request)
    if not request.url.path.startswith("/assets/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response
