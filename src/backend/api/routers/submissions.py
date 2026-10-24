"""Сдача заданий, проверка и журнал оценок."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.dependencies import AuthUser, Connection
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
    return await methods.create_submission(conn, data)


@router.post("/resubmit_work", response_model=SubmissionResponse)
async def resubmit_work(
    submission_id: UUID = Query(...),
    data: SubmissionUpdateRequest = None,
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
    updated = await methods.update_submission(conn, submission_id, data)
    if updated is None:
        raise HTTPException(status_code=404, detail="Сдача не найдена")
    return updated


@router.get("/get_submissions")
async def get_submissions(
    assignment_id: UUID = Query(...),
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
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
    files = await methods.get_files_by_submission(conn, submission_id)
    return {"submission": submission, "files": files}


@router.post("/grade_submission", response_model=SubmissionResponse)
async def grade_submission(
    submission_id: UUID = Query(...),
    data: SubmissionReviewRequest = None,
    user: AuthUser = None,
    conn: Connection = None,
) -> dict[str, Any]:
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
    review_data = SubmissionReviewRequest(
        status="returned",
        feedback=feedback,
        grade=None,
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
