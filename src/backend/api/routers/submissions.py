"""Сдача заданий, проверка и журнал оценок."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.dependencies import AuthUser, Connection, check_is_teacher_or_admin
from backend.api.errors import PROTECTED_ERRORS
from backend.api.access import assignment_access, submission_access, course_access
from backend.db import methods
from backend.schemas.api import GradeSubmissionRequest, SubmissionsResponse, SubmissionDataResponse
from backend.schemas.data import (
    SubmissionCreateRequest,
    SubmissionResponse,
    SubmissionReviewRequest,
    SubmissionUpdateRequest,
)

router = APIRouter(tags=["Сдачи и оценки"], responses=PROTECTED_ERRORS)


@router.post("/submit_work", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
async def submit_work(
    data: SubmissionCreateRequest,
    user: AuthUser,
    conn: Connection,
) -> dict[str, Any]:
    if data.submitted_by != user["id"] and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Нельзя сдать работу от чужого имени")
    if data.status and data.status in ("graded", "returned") and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Студент не может выставлять статус проверки 'graded' или 'returned'")
    if not user.get("is_admin"):
        data = data.model_copy(update={"status": "submitted"})
    assignment, material, staff = await assignment_access(conn, user, data.assignment_id)
    if not user.get("is_admin"):
        _, _, member = await course_access(conn, user, material["discipline_id"])
        if member is None or member["role"] != "student":
            raise HTTPException(403, "Сдавать работу может назначенный студент")
        if assignment["is_team_work"]:
            team = await methods.get_team_by_id(conn, data.team_id) if data.team_id else None
            if not team or team["discipline_id"] != material["discipline_id"] or member.get("team_id") != data.team_id:
                raise HTTPException(403, "Вы не участник указанной команды курса")
        elif data.team_id is not None:
            raise HTTPException(422, "Для индивидуального задания team_id не передаётся")
    if len(data.file_ids) != len(set(data.file_ids)) or not await methods.lock_submission_files(conn, data.file_ids, user["id"]):
        raise HTTPException(403, "Нет доступа к вложениям или загрузка не завершена")
    result = await methods.create_submission(conn, data)
    await methods.attach_submission_files(conn, data.file_ids, result["id"])
    return result


@router.post("/resubmit_work", response_model=SubmissionResponse)
async def resubmit_work(
    submission_id: UUID = Query(...),
    data: SubmissionUpdateRequest = ...,
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    submission = await methods.get_submission_by_id(conn, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Сдача не найдена")
    if submission["submitted_by"] != user["id"] and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Нельзя изменять чужую работу")

    if data.status and data.status in ("graded", "returned") and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Студент не может менять статус на 'graded' или 'returned'")

    if data.status is None or not user.get("is_admin"):
        data = data.model_copy(update={"status": "submitted"})

    await submission_access(conn, user, submission_id)
    if submission["status"] not in ("draft", "returned") and not user.get("is_admin"):
        raise HTTPException(409, "Повторная сдача доступна для черновика или возвращённой работы")
    if len(data.file_ids) != len(set(data.file_ids)) or not await methods.lock_submission_files(conn, data.file_ids, user["id"], submission_id):
        raise HTTPException(403, "Нет доступа к вложениям или загрузка не завершена")
    updated = await methods.update_submission(conn, submission_id, data)
    await methods.attach_submission_files(conn, data.file_ids, submission_id)
    return updated


@router.get("/get_submissions", response_model=SubmissionsResponse)
async def get_submissions(
    assignment_id: UUID = Query(...),
    student_id: UUID | None = Query(None),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    assignment, material, staff = await assignment_access(conn, user, assignment_id)
    target_id = student_id or user["id"]
    if target_id != user["id"] and not staff:
        raise HTTPException(403, "Нельзя запрашивать сдачи другого студента")
    if target_id != user["id"]:
        members = await methods.get_discipline_members(conn, material["discipline_id"])
        if not any(m["user_id"] == target_id and m.get("status") == "active" and m.get("role") == "student" for m in members):
            raise HTTPException(403, "Студент не является участником курса")
    submissions = await methods.get_user_submissions(conn, target_id, assignment_id)
    return {"items": submissions}


@router.get("/get_submission_data", response_model=SubmissionDataResponse)
async def get_submission_data(
    submission_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    submission, _, _ = await submission_access(conn, user, submission_id)

    files = await methods.get_files_by_submission(conn, submission_id)
    return {"submission": submission, "files": files}


@router.post("/grade_submission", response_model=SubmissionResponse)
async def grade_submission(
    submission_id: UUID = Query(...),
    data: GradeSubmissionRequest = ...,
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    submission = await methods.get_submission_by_id(conn, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Сдача не найдена")
    assignment = await methods.get_assignment_by_id(conn, submission["assignment_id"])
    if assignment:
        lesson = await methods.get_lesson_by_id(conn, assignment["lesson_id"])
        disc_id = lesson["discipline_id"] if lesson else None
        if not await check_is_teacher_or_admin(conn, user, disc_id):
            raise HTTPException(status_code=403, detail="Только преподаватель курса может выставлять оценку")
    elif not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Только преподаватель курса может выставлять оценку")

    if assignment is None:
        raise HTTPException(404, "Задание не найдено")
    if data.score > assignment["max_score"]:
        raise HTTPException(422, "Балл не может превышать максимум задания")
    if data and (not data.grader_id or not user.get("is_admin")):
        data = data.model_copy(update={"grader_id": user["id"]})

    reviewed = await methods.review_submission(conn, submission_id, data)
    if reviewed is None:
        raise HTTPException(status_code=404, detail="Сдача не найдена")
    return reviewed


@router.post("/return_submission", response_model=SubmissionResponse)
async def return_submission(
    submission_id: UUID = Query(...),
    feedback: str | None = Query(None),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    submission = await methods.get_submission_by_id(conn, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Сдача не найдена")
    assignment = await methods.get_assignment_by_id(conn, submission["assignment_id"])
    if assignment:
        lesson = await methods.get_lesson_by_id(conn, assignment["lesson_id"])
        disc_id = lesson["discipline_id"] if lesson else None
        if not await check_is_teacher_or_admin(conn, user, disc_id):
            raise HTTPException(status_code=403, detail="Только преподаватель курса может возвращать работу на доработку")
    elif not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Только преподаватель курса может возвращать работу на доработку")

    review_data = SubmissionReviewRequest(
        status="returned",
        feedback=feedback,
        grader_id=user["id"],
        score=None,
    )
    reviewed = await methods.review_submission(conn, submission_id, review_data)
    if reviewed is None:
        raise HTTPException(status_code=404, detail="Сдача не найдена")
    return reviewed


@router.get("/get_grades")
async def get_grades(
    course_id: UUID = Query(...),
    user_id: UUID | None = Query(None),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    _, staff, _ = await course_access(conn, user, course_id)
    target_user_id = user_id or user["id"]
    if target_user_id != user["id"] and not staff:
        raise HTTPException(403, "Нельзя запрашивать оценки другого студента")
    if target_user_id != user["id"]:
        members = await methods.get_discipline_members(conn, course_id)
        if not any(m["user_id"] == target_user_id and m.get("status") == "active" for m in members):
            raise HTTPException(403, "Студент не состоит в курсе")
    grades = await methods.get_student_discipline_grades(conn, course_id, target_user_id)
    return {"items": grades}
