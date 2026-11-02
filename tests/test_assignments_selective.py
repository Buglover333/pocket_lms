"""Тесты для персональной (выборочной) выдачи заданий и передачи ID студентов."""

import unittest
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.api.dependencies import get_connection, require_auth_user
from backend.api.main import app
from backend.db import methods
from backend.schemas.data import (
    AssignmentCreateRequest,
    AssignmentResponse,
    AssignmentUpdateRequest,
)


class AssignmentSchemasUnitTests(unittest.TestCase):
    """Тестирование схем Pydantic для назначения заданий."""

    def test_create_request_accepts_student_ids(self):
        uid1 = uuid4()
        uid2 = uuid4()
        req = AssignmentCreateRequest(
            lesson_id=uuid4(),
            title="Лабораторная работа",
            description_markdown="ТЗ",
            target_type="selective",
            student_ids=[uid1, uid2],
        )
        self.assertEqual(req.target_type, "selective")
        self.assertEqual(req.student_ids, [uid1, uid2])

    def test_create_request_accepts_target_student_ids_alias(self):
        uid = uuid4()
        req = AssignmentCreateRequest.model_validate(
            {
                "lesson_id": str(uuid4()),
                "title": "Индивидуальное задание",
                "description_markdown": "ТЗ",
                "target_type": "selective",
                "target_student_ids": [str(uid)],
            }
        )
        self.assertEqual(req.student_ids, [uid])

    def test_update_request_accepts_member_ids_alias(self):
        uid = uuid4()
        req = AssignmentUpdateRequest.model_validate(
            {
                "is_published": True,
                "target_type": "selective",
                "member_ids": [str(uid)],
            }
        )
        self.assertEqual(req.student_ids, [uid])

    def test_response_includes_student_ids(self):
        aid = uuid4()
        lid = uuid4()
        sid = uuid4()
        resp = AssignmentResponse.model_validate(
            {
                "id": aid,
                "lesson_id": lid,
                "title": "Тест",
                "description_markdown": "Текст",
                "target_type": "selective",
                "is_team_work": False,
                "max_score": 100,
                "due_date": None,
                "template_file_id": None,
                "is_published": True,
                "created_at": "2026-11-01T10:00:00Z",
                "student_ids": [sid],
            }
        )
        self.assertEqual(resp.student_ids, [sid])


class AssignmentMethodsUnitTests(unittest.IsolatedAsyncioTestCase):
    """Тестирование вспомогательных методов разрешения и синхронизации участников."""

    async def test_resolve_course_member_ids_maps_user_and_member_ids(self):
        user_id_1 = uuid4()
        member_id_1 = uuid4()
        user_id_2 = uuid4()
        member_id_2 = uuid4()
        missing_id = uuid4()

        fake_members = [
            {"id": member_id_1, "user_id": user_id_1, "status": "active"},
            {"id": member_id_2, "user_id": user_id_2, "status": "active"},
        ]

        conn = AsyncMock()
        with patch("backend.db.methods.get_discipline_members", return_value=fake_members):
            resolved, missing = await methods.resolve_course_member_ids(
                conn, uuid4(), [user_id_1, member_id_2, missing_id]
            )

            self.assertEqual(set(resolved), {member_id_1, member_id_2})
            self.assertEqual(missing, [missing_id])


class AssignmentEndpointsTests(unittest.TestCase):
    """Интеграционные тесты роутера заданий с проверкой передачи student_ids."""

    def setUp(self):
        self.client = TestClient(app)
        self.teacher_id = uuid4()
        self.teacher_user = {
            "id": self.teacher_id,
            "email": "teacher@pocket-lms.local",
            "name": "Преподаватель",
            "role": "teacher",
            "is_admin": True,
            "is_active": True,
        }
        self.fake_conn = AsyncMock()
        app.dependency_overrides[get_connection] = lambda: self.fake_conn
        app.dependency_overrides[require_auth_user] = lambda: self.teacher_user

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_create_assignment_with_student_ids(self):
        lesson_id = uuid4()
        course_id = uuid4()
        student_id_1 = uuid4()
        student_id_2 = uuid4()
        member_id_1 = uuid4()
        member_id_2 = uuid4()
        assignment_id = uuid4()

        lesson_mock = {"id": lesson_id, "discipline_id": course_id, "title": "Урок 1"}
        created_mock = {
            "id": assignment_id,
            "lesson_id": lesson_id,
            "title": "Индивидуальное задание",
            "description_markdown": "ТЗ",
            "target_type": "selective",
            "is_team_work": False,
            "max_score": 100,
            "due_date": None,
            "template_file_id": None,
            "is_published": True,
            "created_at": "2026-11-01T12:00:00Z",
            "updated_at": None,
        }
        targets_mock = [
            {"id": uuid4(), "assignment_id": assignment_id, "member_id": member_id_1, "user_id": student_id_1},
            {"id": uuid4(), "assignment_id": assignment_id, "member_id": member_id_2, "user_id": student_id_2},
        ]

        with patch("backend.db.methods.get_lesson_by_id", return_value=lesson_mock):
            with patch("backend.api.routers.assignments.check_is_teacher_or_admin", return_value=True):
                with patch("backend.db.methods.resolve_course_member_ids", return_value=([member_id_1, member_id_2], [])):
                    with patch("backend.db.methods.create_assignment", return_value=created_mock):
                        with patch("backend.db.methods.set_assignment_targets", return_value=targets_mock):
                            resp = self.client.post(
                                "/create_assignment",
                                json={
                                    "lesson_id": str(lesson_id),
                                    "title": "Индивидуальное задание",
                                    "description_markdown": "ТЗ",
                                    "target_type": "selective",
                                    "student_ids": [str(student_id_1), str(student_id_2)],
                                },
                                headers={"Authorization": "Bearer dev-token"},
                            )
                            self.assertEqual(resp.status_code, 201, resp.text)
                            data = resp.json()
                            self.assertEqual(data["target_type"], "selective")
                            self.assertEqual(len(data["student_ids"]), 2)
                            self.assertIn(str(student_id_1), data["student_ids"])
                            self.assertIn(str(student_id_2), data["student_ids"])

    def test_create_assignment_with_unknown_student_returns_422(self):
        lesson_id = uuid4()
        course_id = uuid4()
        unknown_student = uuid4()

        lesson_mock = {"id": lesson_id, "discipline_id": course_id, "title": "Урок 1"}

        with patch("backend.db.methods.get_lesson_by_id", return_value=lesson_mock):
            with patch("backend.api.routers.assignments.check_is_teacher_or_admin", return_value=True):
                with patch("backend.db.methods.resolve_course_member_ids", return_value=([], [unknown_student])):
                    resp = self.client.post(
                        "/create_assignment",
                        json={
                            "lesson_id": str(lesson_id),
                            "title": "Задание",
                            "description_markdown": "ТЗ",
                            "target_type": "selective",
                            "student_ids": [str(unknown_student)],
                        },
                        headers={"Authorization": "Bearer dev-token"},
                    )
                    self.assertEqual(resp.status_code, 422)
                    self.assertIn("Студенты не найдены", resp.json()["detail"])

    def test_update_assignment_publishing_with_student_ids(self):
        assignment_id = uuid4()
        lesson_id = uuid4()
        course_id = uuid4()
        student_id = uuid4()
        member_id = uuid4()

        existing_assignment = {
            "id": assignment_id,
            "lesson_id": lesson_id,
            "title": "Черновик",
            "description_markdown": "ТЗ",
            "target_type": "all",
            "is_published": False,
        }
        lesson_mock = {"id": lesson_id, "discipline_id": course_id}
        updated_mock = {
            **existing_assignment,
            "target_type": "selective",
            "is_published": True,
            "created_at": "2026-11-01T12:00:00Z",
        }
        targets_mock = [
            {"id": uuid4(), "assignment_id": assignment_id, "member_id": member_id, "user_id": student_id}
        ]

        with patch("backend.db.methods.get_assignment_by_id", return_value=existing_assignment):
            with patch("backend.db.methods.get_lesson_by_id", return_value=lesson_mock):
                with patch("backend.api.routers.assignments.check_is_teacher_or_admin", return_value=True):
                    with patch("backend.db.methods.resolve_course_member_ids", return_value=([member_id], [])):
                        with patch("backend.db.methods.update_assignment", return_value=updated_mock):
                            with patch("backend.db.methods.set_assignment_targets", return_value=targets_mock):
                                resp = self.client.patch(
                                    "/update_assignment",
                                    params={"assignment_id": str(assignment_id)},
                                    json={
                                        "is_published": True,
                                        "target_type": "selective",
                                        "student_ids": [str(student_id)],
                                    },
                                    headers={"Authorization": "Bearer dev-token"},
                                )
                                self.assertEqual(resp.status_code, 200, resp.text)
                                data = resp.json()
                                self.assertEqual(data["is_published"], True)
                                self.assertEqual(data["target_type"], "selective")
                                self.assertEqual(data["student_ids"], [str(student_id)])

    def test_update_assignment_switching_to_all_clears_targets(self):
        assignment_id = uuid4()
        lesson_id = uuid4()
        course_id = uuid4()

        existing_assignment = {
            "id": assignment_id,
            "lesson_id": lesson_id,
            "title": "Селективное задание",
            "description_markdown": "ТЗ",
            "target_type": "selective",
            "is_published": True,
        }
        lesson_mock = {"id": lesson_id, "discipline_id": course_id}
        updated_mock = {
            **existing_assignment,
            "target_type": "all",
            "created_at": "2026-11-01T12:00:00Z",
        }

        with patch("backend.db.methods.get_assignment_by_id", return_value=existing_assignment):
            with patch("backend.db.methods.get_lesson_by_id", return_value=lesson_mock):
                with patch("backend.api.routers.assignments.check_is_teacher_or_admin", return_value=True):
                    with patch("backend.db.methods.update_assignment", return_value=updated_mock):
                        with patch("backend.db.methods.clear_assignment_targets") as mock_clear:
                            resp = self.client.patch(
                                "/update_assignment",
                                params={"assignment_id": str(assignment_id)},
                                json={"target_type": "all"},
                                headers={"Authorization": "Bearer dev-token"},
                            )
                            self.assertEqual(resp.status_code, 200, resp.text)
                            self.assertEqual(resp.json()["target_type"], "all")
                            self.assertEqual(resp.json()["student_ids"], [])
                            mock_clear.assert_called_once_with(self.fake_conn, assignment_id)


if __name__ == "__main__":
    unittest.main()
