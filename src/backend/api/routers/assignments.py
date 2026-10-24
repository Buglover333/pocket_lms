"""Задания и календарь дедлайнов."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.dependencies import AuthUser, Connection, check_is_teacher_or_admin
from backend.api.errors import PROTECTED_ERRORS
from backend.db import methods
from backend.schemas.data import (
    AssignmentCreateRequest,
    AssignmentResponse,
    AssignmentUpdateRequest,
)

router = APIRouter(tags=["Задания"], responses=PROTECTED_ERRORS)


@router.get("/get_assignments")
async def get_assignments(
    lesson_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    assignments = await methods.get_assignments_by_lesson(conn, lesson_id)
    return {"items": assignments}


@router.get("/get_assignment_data")
async def get_assignment_data(
    assignment_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    assignment = await methods.get_assignment_by_id(conn, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    targets = await methods.get_assignment_targets(conn, assignment_id)
    return {"assignment": assignment, "targets": targets}


@router.post("/create_assignment", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    data: AssignmentCreateRequest,
    user: AuthUser,
    conn: Connection,
) -> dict[str, Any]:
    lesson = await methods.get_lesson_by_id(conn, data.lesson_id)
    disc_id = lesson["discipline_id"] if lesson else None
    if not await check_is_teacher_or_admin(conn, user, disc_id):
        raise HTTPException(status_code=403, detail="Только преподаватель курса может создавать задания")
    return await methods.create_assignment(conn, data)


@router.patch("/update_assignment", response_model=AssignmentResponse)
async def update_assignment(
    assignment_id: UUID = Query(...),
    data: AssignmentUpdateRequest = None,
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    assignment = await methods.get_assignment_by_id(conn, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    lesson = await methods.get_lesson_by_id(conn, assignment["lesson_id"])
    disc_id = lesson["discipline_id"] if lesson else None
    if not await check_is_teacher_or_admin(conn, user, disc_id):
        raise HTTPException(status_code=403, detail="Только преподаватель курса может редактировать задания")
    updated = await methods.update_assignment(conn, assignment_id, data)
    return updated


@router.delete("/delete_assignment")
async def delete_assignment(
    assignment_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    assignment = await methods.get_assignment_by_id(conn, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    lesson = await methods.get_lesson_by_id(conn, assignment["lesson_id"])
    disc_id = lesson["discipline_id"] if lesson else None
    if not await check_is_teacher_or_admin(conn, user, disc_id):
        raise HTTPException(status_code=403, detail="Только преподаватель курса может удалять задания")
    deleted = await methods.delete_assignment(conn, assignment_id)
    return {"ok": True}


@router.get("/get_calendar")
async def get_calendar(
    course_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    deadlines = await methods.get_discipline_deadlines(conn, course_id)
    return {"items": deadlines}
