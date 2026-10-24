"""Материалы и уроки курсов."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.dependencies import AuthUser, Connection, check_is_teacher_or_admin
from backend.api.errors import PROTECTED_ERRORS
from backend.db import methods
from backend.schemas.data import LessonCreateRequest, LessonResponse, LessonUpdateRequest

router = APIRouter(tags=["Уроки и материалы"], responses=PROTECTED_ERRORS)


@router.get("/get_materials")
async def get_materials(
    course_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    lessons = await methods.get_lessons_by_discipline(conn, course_id)
    return {"items": lessons}


@router.get("/get_material_data")
async def get_material_data(
    material_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    lesson = await methods.get_lesson_by_id(conn, material_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Материал не найден")
    files = await methods.get_files_by_lesson(conn, material_id)
    return {"material": lesson, "files": files}


@router.post("/create_material", response_model=LessonResponse, status_code=status.HTTP_201_CREATED)
async def create_material(
    data: LessonCreateRequest,
    user: AuthUser,
    conn: Connection,
) -> dict[str, Any]:
    if not await check_is_teacher_or_admin(conn, user, data.discipline_id):
        raise HTTPException(status_code=403, detail="Только преподаватель курса может создавать материалы")
    return await methods.create_lesson(conn, data)


@router.patch("/update_material", response_model=LessonResponse)
async def update_material(
    material_id: UUID = Query(...),
    data: LessonUpdateRequest = ...,
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    lesson = await methods.get_lesson_by_id(conn, material_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Материал не найден")
    if not await check_is_teacher_or_admin(conn, user, lesson["discipline_id"]):
        raise HTTPException(status_code=403, detail="Только преподаватель курса может изменять материалы")
    updated = await methods.update_lesson(conn, material_id, data)
    return updated


@router.delete("/delete_material")
async def delete_material(
    material_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    lesson = await methods.get_lesson_by_id(conn, material_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Материал не найден")
    if not await check_is_teacher_or_admin(conn, user, lesson["discipline_id"]):
        raise HTTPException(status_code=403, detail="Только преподаватель курса может удалять материалы")
    deleted = await methods.delete_lesson(conn, material_id)
    return {"ok": True}
