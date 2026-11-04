"""Задания и календарь дедлайнов."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.access import (
    assignment_access,
    can_delete_content,
    course_access,
    material_access,
)
from backend.api.dependencies import AuthUser, Connection, check_is_teacher_or_admin
from backend.api.errors import PROTECTED_ERRORS
from backend.db import methods
from backend.schemas.api import AssignmentDataResponse
from backend.schemas.data import (
    AssignmentCreateRequest,
    AssignmentResponse,
    AssignmentUpdateRequest,
)
from backend.schemas.identity import SuccessResponse

router = APIRouter(tags=["Задания"], responses=PROTECTED_ERRORS)


@router.get("/get_assignments", response_model=list[AssignmentResponse])
async def get_assignments(
    lesson_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    _, staff = await material_access(conn, user, lesson_id)
    assignments = await methods.get_assignments_by_lesson(conn, lesson_id)
    visible = []
    for item in assignments:
        if staff:
            visible.append(item)
            continue
        try:
            await assignment_access(conn, user, item["id"])
            visible.append(item)
        except HTTPException as exc:
            if exc.status_code != 403:
                raise
    return visible


@router.get("/get_assignment_data", response_model=AssignmentDataResponse)
async def get_assignment_data(
    assignment_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    assignment, _, staff = await assignment_access(conn, user, assignment_id)
    targets = await methods.get_assignment_targets(conn, assignment_id) if staff else []
    return {"assignment": assignment, "targets": targets}


@router.post(
    "/create_assignment",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_assignment(
    data: AssignmentCreateRequest,
    user: AuthUser,
    conn: Connection,
) -> dict[str, Any]:
    lesson = await methods.get_lesson_by_id(conn, data.lesson_id)
    if lesson is None:
        raise HTTPException(404, "Материал не найден")
    disc_id = lesson["discipline_id"]
    if not await check_is_teacher_or_admin(conn, user, disc_id):
        raise HTTPException(
            status_code=403, detail="Только преподаватель курса может создавать задания"
        )

    if data.student_ids and data.target_type == "all":
        data = data.model_copy(update={"target_type": "selective"})

    resolved_members: list[UUID] = []
    if data.student_ids is not None:
        resolved_members, missing = await methods.resolve_course_member_ids(
            conn, disc_id, data.student_ids
        )
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"Студенты не найдены среди участников курса: {', '.join(str(m) for m in missing)}",
            )

    created = await methods.create_assignment(conn, data, created_by=user["id"])

    if data.student_ids is not None:
        targets = await methods.set_assignment_targets(
            conn, created["id"], resolved_members
        )
        created = {**created, "student_ids": [t["user_id"] for t in targets]}

    return created


@router.patch("/update_assignment", response_model=AssignmentResponse)
async def update_assignment(
    assignment_id: UUID = Query(...),
    data: AssignmentUpdateRequest = ...,
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    assignment = await methods.get_assignment_by_id(conn, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    lesson = await methods.get_lesson_by_id(conn, assignment["lesson_id"])
    if lesson is None:
        raise HTTPException(404, "Материал не найден")
    disc_id = lesson["discipline_id"]
    if not await check_is_teacher_or_admin(conn, user, disc_id):
        raise HTTPException(
            status_code=403,
            detail="Только преподаватель курса может редактировать задания",
        )

    if (
        data.student_ids is not None
        and data.target_type is None
        and assignment.get("target_type") != "selective"
    ):
        data = data.model_copy(update={"target_type": "selective"})

    resolved_members: list[UUID] | None = None
    if data.student_ids is not None:
        resolved_members, missing = await methods.resolve_course_member_ids(
            conn, disc_id, data.student_ids
        )
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"Студенты не найдены среди участников курса: {', '.join(str(m) for m in missing)}",
            )

    updated = await methods.update_assignment(conn, assignment_id, data)

    if resolved_members is not None:
        targets = await methods.set_assignment_targets(
            conn, assignment_id, resolved_members
        )
        updated = {**updated, "student_ids": [t["user_id"] for t in targets]}
    elif data.target_type == "all":
        await methods.clear_assignment_targets(conn, assignment_id)
        updated = {**updated, "student_ids": []}
    elif updated.get("target_type") == "selective":
        targets = await methods.get_assignment_targets(conn, assignment_id)
        updated = {**updated, "student_ids": [t["user_id"] for t in targets]}

    return updated


@router.delete("/delete_assignment", response_model=SuccessResponse)
async def delete_assignment(
    assignment_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    assignment = await methods.get_assignment_by_id(conn, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    lesson = await methods.get_lesson_by_id(conn, assignment["lesson_id"])
    if lesson is None:
        raise HTTPException(404, "Материал не найден")
    disc_id = lesson["discipline_id"]
    if not await can_delete_content(conn, user, assignment, disc_id):
        raise HTTPException(403, "Удалять задание может его автор или создатель модуля")
    deleted = await methods.delete_assignment(conn, assignment_id)
    return {"ok": True}


@router.get("/get_calendar")
async def get_calendar(
    course_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    _, staff, _ = await course_access(conn, user, course_id)
    deadlines = await methods.get_discipline_deadlines(conn, course_id)
    visible = []
    for item in deadlines:
        if staff:
            visible.append(item)
            continue
        try:
            await assignment_access(conn, user, item["id"])
            visible.append(item)
        except HTTPException as exc:
            if exc.status_code != 403:
                raise
    return {"items": visible}
