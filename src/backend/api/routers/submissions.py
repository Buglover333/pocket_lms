"""Сдача заданий, проверка и журнал оценок."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.dependencies import AuthUser, Connection, check_is_teacher_or_admin
from backend.api.errors import PROTECTED_ERRORS
from backend.db import methods
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
    return await methods.create_submission(conn, data)


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

    if data.status is None:
        data = data.model_copy(update={"status": "submitted"})

    updated = await methods.update_submission(conn, submission_id, data)
    return updated


@router.get("/get_submissions")
async def get_submissions(
    assignment_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    assignment = await methods.get_assignment_by_id(conn, assignment_id)
    if assignment:
        lesson = await methods.get_lesson_by_id(conn, assignment["lesson_id"])
        disc_id = lesson["discipline_id"] if lesson else None
        if not await check_is_teacher_or_admin(conn, user, disc_id):
            raise HTTPException(status_code=403, detail="Только преподаватель может просматривать все сданные работы")
    submissions = await methods.get_submissions_by_assignment(conn, assignment_id)
    return {"items": submissions}


@router.get("/get_submission_data")
async def get_submission_data(
    submission_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    submission = await methods.get_submission_by_id(conn, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Сдача не найдена")

    is_author = submission["submitted_by"] == user["id"]
    is_teammate = False
    if submission.get("team_id"):
        team_members = await methods.get_team_members(conn, submission["team_id"])
        is_teammate = any(m["user_id"] == user["id"] for m in team_members)

    is_teacher = False
    assignment = await methods.get_assignment_by_id(conn, submission["assignment_id"])
    if assignment:
        lesson = await methods.get_lesson_by_id(conn, assignment["lesson_id"])
        disc_id = lesson["discipline_id"] if lesson else None
        is_teacher = await check_is_teacher_or_admin(conn, user, disc_id)
    elif user.get("is_admin"):
        is_teacher = True

    if not (is_author or is_teammate or is_teacher or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="Нельзя просматривать чужую работу")

    files = await methods.get_files_by_submission(conn, submission_id)
    return {"submission": submission, "files": files}


@router.post("/grade_submission", response_model=SubmissionResponse)
async def grade_submission(
    submission_id: UUID = Query(...),
    data: SubmissionReviewRequest = ...,
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
    target_user_id = user_id if (user_id and user.get("is_admin")) else user["id"]
    grades = await methods.get_student_discipline_grades(conn, course_id, target_user_id)
    return {"items": grades}
