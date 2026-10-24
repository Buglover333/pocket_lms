"""API contract checks against a dedicated PostgreSQL database.

Requires TEST_DATABASE_URL with a database name starting with pocket_lms_api_test_.
The suite creates its own records and removes those records after each check.
"""

import asyncio
import os
import secrets
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import jwt
import psycopg
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from backend.api.main import app
from backend.db import methods
from backend.api.security import hash_password, make_token, verify_password

PROTECTED = ("/get_courses", "/get_modules", "/get_user_info")
PASSWORD = "Password123"


class APIContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url = os.getenv("TEST_DATABASE_URL", "")
        if not url or not conninfo_to_dict(url).get("dbname", "").startswith("pocket_lms_api_test_"):
            raise RuntimeError("Set TEST_DATABASE_URL to a dedicated pocket_lms_api_test_* database")
        cls.environment = patch.dict(os.environ, DATABASE_URL=url, JWT_SECRET=secrets.token_urlsafe(48))
        cls.environment.start()
        cls.addClassCleanup(cls.environment.stop)
        cls.db = psycopg.connect(url, autocommit=True, row_factory=dict_row)
        cls.addClassCleanup(cls.db.close)
        cls.password_hash = hash_password(PASSWORD)

    def setUp(self):
        self.client = self.enterContext(TestClient(app))
        self.user_ids = []
        self.addCleanup(self.cleanup_rows)
        self.user = self.create_user()
        self.other = self.create_user()
        self.headers = {"Authorization": "Bearer " + make_token(self.user["id"])}

    def cleanup_rows(self):
        for user_id in self.user_ids:
            self.db.execute("DELETE FROM disciplines WHERE author_id = %s", (user_id,))
        for user_id in self.user_ids:
            self.db.execute("DELETE FROM modules WHERE curator_id = %s", (user_id,))
        for user_id in self.user_ids:
            self.db.execute("DELETE FROM users WHERE id = %s", (user_id,))

    def create_user(self):
        user = self.db.execute(
            """INSERT INTO users (email, password_hash, first_name, last_name, middle_name, yandex_id)
               VALUES (%s, %s, 'Иван', 'Иванов', 'Иванович', %s) RETURNING *""",
            (f"api-{uuid4().hex}@example.com", self.password_hash, "test-" + uuid4().hex),
        ).fetchone()
        self.user_ids.append(user["id"])
        return user

    def registration(self, **changes):
        body = {
            "email": f"api-{uuid4().hex}@example.com",
            "first_name": " Анна ",
            "last_name": " Тест ",
            "password": PASSWORD,
            "password_confirm": PASSWORD,
        }
        body.update(changes)
        return body

    def get(self, path, user_id=None, headers=None):
        return self.client.get(
            path,
            params={"user_id": user_id or self.user["id"]},
            headers=self.headers if headers is None else headers,
        )

    def assert_error(self, response, code):
        self.assertEqual(response.status_code, code, response.text)
        self.assertEqual(set(response.json()), {"detail"})
        self.assertIsInstance(response.json()["detail"], str)

    def test_registration_response_and_password_storage(self):
        body = self.registration()
        response = self.client.post("/register", json=body)
        self.assertEqual(response.status_code, 201, response.text)
        user = response.json()
        self.user_ids.append(UUID(user["id"]))
        self.assertEqual(set(user), {"id", "email", "first_name", "last_name", "is_active", "created_at"})
        self.assertEqual((user["first_name"], user["last_name"]), ("Анна", "Тест"))
        self.assertTrue(user["is_active"])
        stored = self.db.execute("SELECT password_hash FROM users WHERE id = %s", (user["id"],)).fetchone()
        self.assertNotEqual(stored["password_hash"], PASSWORD)
        self.assertTrue(verify_password(PASSWORD, stored["password_hash"]))

    def test_registration_validation(self):
        invalid = (
            {"email": "wrong"}, {"email": "a@@example.com"}, {"first_name": "  "},
            {"last_name": ""}, {"password": "short1A", "password_confirm": "short1A"},
            {"password": "lowercase123", "password_confirm": "lowercase123"},
            {"password": "NoDigitsHere", "password_confirm": "NoDigitsHere"},
            {"password": "A1" * 33, "password_confirm": "A1" * 33},
            {"password_confirm": "Different123"}, {"is_admin": True},
        )
        for changes in invalid:
            with self.subTest(fields=list(changes)):
                self.assert_error(self.client.post("/register", json=self.registration(**changes)), 422)
        missing = self.registration()
        missing.pop("first_name")
        self.assert_error(self.client.post("/register", json=missing), 422)

    def test_duplicate_email_including_different_case(self):
        self.assert_error(self.client.post("/register", json=self.registration(email=self.user["email"].upper())), 409)
        self.db.execute("UPDATE users SET email = upper(email) WHERE id = %s", (self.user["id"],))
        self.assert_error(self.client.post("/register", json=self.registration(email=self.user["email"])), 409)

    def test_concurrent_registration_same_email(self):
        body = self.registration()
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(lambda _: self.client.post("/register", json=body), range(2)))
        for response in responses:
            if response.status_code == 201:
                self.user_ids.append(UUID(response.json()["id"]))
        self.assertEqual(sorted(response.status_code for response in responses), [201, 409])

    def test_authentication_response_and_invalid_credentials(self):
        response = self.client.post("/auth", json={"email": self.user["email"].upper(), "password": PASSWORD})
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(set(data), {"access_token", "token_type", "user_id"})
        self.assertEqual(data["user_id"], str(self.user["id"]))
        self.assertEqual(data["token_type"], "bearer")
        self.assertEqual(self.get("/get_user_info", headers={"Authorization": "Bearer " + data["access_token"]}).status_code, 200)
        for email, password in ((self.user["email"], "Wrong123"), ("missing@example.com", PASSWORD)):
            self.assert_error(self.client.post("/auth", json={"email": email, "password": password}), 401)
        self.assert_error(self.client.post("/auth", json={"email": "wrong", "password": PASSWORD}), 422)
        self.assert_error(self.client.post("/auth", json={"email": self.user["email"]}), 422)
        self.db.execute("UPDATE users SET password_hash = NULL WHERE id = %s", (self.user["id"],))
        self.assert_error(self.client.post("/auth", json={"email": self.user["email"], "password": PASSWORD}), 401)

    def test_empty_courses_and_modules(self):
        for path in PROTECTED[:2]:
            response = self.get(path)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json(), {"items": []})

    def test_active_courses_fields_and_distinct_modules(self):
        module = self.db.execute(
            "INSERT INTO modules (title, description, curator_id) VALUES ('Программа', 'Описание', %s) RETURNING id",
            (self.other["id"],),
        ).fetchone()["id"]
        excluded_module = self.db.execute(
            "INSERT INTO modules (title, curator_id) VALUES ('Чужой модуль', %s) RETURNING id",
            (self.other["id"],),
        ).fetchone()["id"]
        included = []
        team_id = None
        for index, (module_id, membership, role, course_status) in enumerate((
            (module, "active", "student", "published"),
            (module, "active", "teacher", "draft"),
            (None, "active", "owner", "archived"),
            (excluded_module, "left", "student", "published"),
            (excluded_module, "invited", "student", "published"),
            (excluded_module, "other", "student", "published"),
            (excluded_module, "none", "student", "published"),
        )):
            course = self.db.execute(
                """INSERT INTO disciplines (author_id, module_id, title, invite_code, status)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                (self.other["id"], module_id, f"Курс {index}", uuid4().hex, course_status),
            ).fetchone()["id"]
            current_team = None
            if index == 0:
                team_id = self.db.execute(
                    "INSERT INTO teams (discipline_id, name) VALUES (%s, 'Команда') RETURNING id", (course,),
                ).fetchone()["id"]
                current_team = team_id
            if membership != "none":
                self.db.execute(
                    "INSERT INTO discipline_members (discipline_id, user_id, role, status, team_id) VALUES (%s, %s, %s, %s, %s)",
                    (course, self.other["id"] if membership == "other" else self.user["id"], role,
                     "active" if membership == "other" else membership, current_team),
                )
            if membership == "active":
                included.append(str(course))
        async def get_all_memberships():
            async with await psycopg.AsyncConnection.connect(os.environ["DATABASE_URL"]) as conn:
                return await methods.get_user_disciplines(conn, self.user["id"])

        # Existing CRUD callers still receive active, invited and left memberships.
        all_memberships = asyncio.run(get_all_memberships())
        self.assertEqual(len(all_memberships), 5)
        response = self.get("/get_courses")
        self.assertEqual(response.status_code, 200, response.text)
        items = response.json()["items"]
        self.assertCountEqual([item["id"] for item in items], included)
        for item in items:
            self.assertEqual(set(item), {"id", "module_id", "author_id", "title", "discipline_type", "status",
                                         "description", "cover_file_id", "ends_at", "role", "team_id"})
        first = next(item for item in items if item["id"] == included[0])
        self.assertEqual((first["role"], first["team_id"]), ("student", str(team_id)))
        response = self.get("/get_modules")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"items": [{"id": str(module), "title": "Программа", "description": "Описание", "curator_id": str(self.other["id"])}]})

    def test_profile_has_only_public_fields(self):
        response = self.get("/get_user_info")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(set(data), {"id", "email", "first_name", "last_name", "middle_name", "avatar_id", "is_admin", "is_active", "created_at", "updated_at"})
        self.assertEqual(data["middle_name"], "Иванович")
        self.assertIsNone(data["updated_at"])
        self.assertIsNone(data["avatar_id"])

    def test_missing_or_invalid_token(self):
        now = datetime.now(timezone.utc)
        claims = {"sub": str(self.user["id"]), "iat": now, "exp": now + timedelta(hours=1)}
        bad_tokens = [
            "wrong", "Bearer " + self.headers["Authorization"],
            jwt.encode(claims, "wrong-signing-key-" + "x" * 32, algorithm="HS256"),
            jwt.encode({**claims, "exp": now - timedelta(seconds=1)}, os.environ["JWT_SECRET"], algorithm="HS256"),
            jwt.encode({"sub": str(self.user["id"])}, os.environ["JWT_SECRET"], algorithm="HS256"),
            jwt.encode({**claims, "sub": "invalid-uuid"}, os.environ["JWT_SECRET"], algorithm="HS256"),
        ]
        for path in PROTECTED:
            self.assert_error(self.get(path, headers={}), 401)
            self.assert_error(self.get(path, headers={"Authorization": "Basic dGVzdA=="}), 401)
            for token in bad_tokens:
                with self.subTest(path=path, token_kind=bad_tokens.index(token)):
                    self.assert_error(self.get(path, headers={"Authorization": "Bearer " + token}), 401)

    def test_forbidden_user_and_invalid_uuid(self):
        for path in PROTECTED:
            self.assert_error(self.get(path, user_id=self.other["id"]), 403)
            self.assert_error(self.get(path, user_id="not-a-uuid"), 422)
            self.assert_error(self.client.get(path, headers=self.headers), 422)

    def test_missing_or_inactive_user(self):
        missing_id = uuid4()
        missing_headers = {"Authorization": "Bearer " + make_token(missing_id)}
        for path in PROTECTED:
            self.assert_error(self.get(path, user_id=missing_id, headers=missing_headers), 404)
        self.db.execute("UPDATE users SET is_active = FALSE WHERE id = %s", (self.user["id"],))
        for path in PROTECTED:
            self.assert_error(self.get(path), 404)
        self.assert_error(self.client.post("/auth", json={"email": self.user["email"], "password": PASSWORD}), 401)

    def test_app_returns_html_without_database(self):
        with tempfile.TemporaryDirectory() as folder:
            index = Path(folder) / "index.html"
            html = "<!doctype html><html><body>Test frontend fixture</body></html>"
            index.write_text(html)
            with patch("backend.api.routers.frontend.FRONTEND_DIR", Path(folder)), patch.dict(os.environ, DATABASE_URL=""):
                response = self.client.post("/app")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertTrue(response.headers["content-type"].startswith("text/html"))
            self.assertEqual(response.text, html)

    def test_app_without_build_reports_unavailable(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("backend.api.routers.frontend.FRONTEND_DIR", Path(folder)), patch.dict(os.environ, DATABASE_URL=""):
                self.assert_error(self.client.post("/app"), 503)

    def test_openapi_describes_the_contract(self):
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        self.assertTrue({"/app", "/auth", "/register", *PROTECTED}.issubset(set(paths)))
        self.assertIn("text/html", paths["/app"]["post"]["responses"]["200"]["content"])
        for path in PROTECTED:
            self.assertTrue(paths[path]["get"]["security"])
            self.assertTrue({"401", "403", "404", "422"}.issubset(paths[path]["get"]["responses"]))

    def test_update_material_without_body_returns_422(self):
        response = self.client.patch(
            "/update_material",
            params={"material_id": str(uuid4())},
            headers=self.headers,
        )
        self.assert_error(response, 422)

    def test_cannot_edit_course_without_teacher_permission_returns_403(self):
        course = self.db.execute(
            """INSERT INTO disciplines (author_id, title, discipline_type, status, invite_code)
               VALUES (%s, 'Тестовый курс', 'module', 'published', %s) RETURNING *""",
            (self.other["id"], uuid4().hex[:30]),
        ).fetchone()
        response = self.client.patch(
            "/update_course",
            params={"course_id": str(course["id"])},
            json={"title": "Взломанный курс"},
            headers=self.headers,
        )
        self.assert_error(response, 403)

    def test_cannot_submit_work_for_other_user_returns_403(self):
        response = self.client.post(
            "/submit_work",
            json={
                "assignment_id": str(uuid4()),
                "submitted_by": str(self.other["id"]),
                "answer_text": "Чужой ответ",
            },
            headers=self.headers,
        )
        self.assert_error(response, 403)



if __name__ == "__main__":
    unittest.main()
