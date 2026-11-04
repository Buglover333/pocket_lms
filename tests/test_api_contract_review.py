"""Approved analyst contract, profile privacy and production authentication regressions."""

import unittest
from uuid import uuid4, UUID
from fastapi.testclient import TestClient
from pydantic import ValidationError
import test_api as fixtures
import test_api_identity as helpers
from backend.api.main import app
from backend.schemas.api import GradeResponse


class AnalystContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.APIContractTests.setUpClass.__func__(cls)

    create_user = fixtures.APIContractTests.create_user
    token = fixtures.APIContractTests.token
    assert_error = fixtures.APIContractTests.assert_error
    course = helpers.IdentityTests.course
    module = helpers.IdentityTests.module
    staff = helpers.IdentityTests.staff
    invitation = helpers.IdentityTests.invitation
    accept = helpers.IdentityTests.accept
    login = helpers.IdentityTests.login

    def setUp(self):
        fixtures.APIContractTests.setUp(self)
        self.db.execute("DELETE FROM auth_rate_limits")

    def cleanup_rows(self):
        for uid in self.user_ids:
            self.db.execute("DELETE FROM files WHERE uploader_id=%s", (uid,))
        fixtures.APIContractTests.cleanup_rows(self)

    def file(self, owner=None, kind="image", **kwargs):
        return self.db.execute(
            "INSERT INTO files(uploader_id,file_type,url,meta) VALUES (%s,%s,'https://example.com/avatar.png',%s::jsonb) RETURNING id",
            ((owner or self.user)["id"], kind, kwargs.get("meta")),
        ).fetchone()["id"]

    def material(self, course):
        return self.db.execute(
            "INSERT INTO lessons(discipline_id,title) VALUES (%s,'Материал') RETURNING id",
            (course["id"],),
        ).fetchone()["id"]

    def member(self, course, user=None, team=None, status="active"):
        return self.db.execute(
            "INSERT INTO discipline_members(discipline_id,user_id,team_id,status) VALUES (%s,%s,%s,%s) RETURNING id",
            (course["id"], (user or self.user)["id"], team, status),
        ).fetchone()["id"]

    def test_registration_provider_allowlist_exact_match(self):
        for domain in [
            "mail.ru",
            "ya.ru",
            "yandex.ru",
            "yandex.com",
            "vk.com",
            "rambler.ru",
            "bk.ru",
        ]:
            body = fixtures.APIContractTests.registration(
                self, email=f"api-{uuid4().hex}@{domain}"
            )
            r = self.client.post("/register", json=body)
            self.assertEqual(r.status_code, 201, r.text)
            self.user_ids.append(UUID(r.json()["id"]))
        for domain in [
            "gmail.com",
            "outlook.com",
            "example.ru",
            "yandex.ru.evil.com",
            "mail.ru.attacker.ru",
        ]:
            body = fixtures.APIContractTests.registration(
                self, email=f"api-{uuid4().hex}@{domain}"
            )
            self.assert_error(self.client.post("/register", json=body), 422)

    def test_existing_external_email_can_still_log_in(self):
        email = f"legacy-{uuid4().hex}@example.com"
        self.db.execute(
            "UPDATE users SET email=%s WHERE id=%s", (email, self.user["id"])
        )
        self.assertEqual(
            self.client.post(
                "/auth", json={"email": email, "password": fixtures.PASSWORD}
            ).status_code,
            200,
        )

    def test_profile_middle_name_avatar_and_clear(self):
        fid = self.file()
        r = self.client.patch(
            "/update_settings",
            json={"middle_name": "  Петровна  ", "avatar_id": str(fid)},
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["middle_name"], "Петровна")
        self.assertEqual(r.json()["avatar_id"], str(fid))
        r = self.client.patch(
            "/update_settings",
            json={"middle_name": None, "avatar_id": None},
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsNone(r.json()["avatar_id"])
        self.assertIsNone(r.json()["middle_name"])

    def test_avatar_rejects_foreign_nonimage_and_pending(self):
        for fid, code in [
            (self.file(self.other), 403),
            (self.file(kind="document"), 422),
            (self.file(meta='{"storage":"s3","upload_status":"pending"}'), 409),
            (uuid4(), 404),
        ]:
            self.assert_error(
                self.client.patch(
                    "/update_settings",
                    json={"avatar_id": str(fid)},
                    headers=self.headers,
                ),
                code,
            )

    def test_avatar_visible_only_to_shared_course_members(self):
        fid = self.file(self.other)
        self.db.execute(
            "UPDATE users SET avatar_id=%s WHERE id=%s", (fid, self.other["id"])
        )
        self.assert_error(
            self.client.get("/get_file", params={"file_id": fid}, headers=self.headers),
            403,
        )
        c = self.course()
        self.member(c)
        self.assertEqual(
            self.client.get(
                "/get_file", params={"file_id": fid}, headers=self.headers
            ).status_code,
            200,
        )
        self.assert_error(
            self.client.delete(
                "/delete_file", params={"file_id": fid}, headers=self.headers
            ),
            403,
        )

    def test_delete_account_is_soft_and_revokes_every_session(self):
        h, _ = self.login()
        with TestClient(app) as second:
            h2, _ = self.login(client=second)
            self.assert_error(
                self.client.request(
                    "DELETE",
                    "/delete_account",
                    json={"current_password": "Wrong123"},
                    headers=h,
                ),
                401,
            )
            r = self.client.request(
                "DELETE",
                "/delete_account",
                json={"current_password": fixtures.PASSWORD},
                headers=h,
            )
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(r.json(), {"ok": True})
            self.assert_error(second.get("/auth/sessions", headers=h2), 401)
            self.assert_error(
                second.post("/auth/refresh", headers={"X-Requested-With": "PocketLMS"}),
                401,
            )
        self.assertFalse(
            self.db.execute(
                "SELECT is_active FROM users WHERE id=%s", (self.user["id"],)
            ).fetchone()["is_active"]
        )

    def test_course_create_status_and_server_generated_code(self):
        body = {"author_id": str(self.user["id"]), "title": "Новый"}
        self.assert_error(
            self.client.post("/create_course", json=body, headers=self.headers), 422
        )
        for field in [
            {"status": "archived"},
            {"status": "draft", "invite_code": "MY-CODE"},
        ]:
            self.assert_error(
                self.client.post(
                    "/create_course", json={**body, **field}, headers=self.headers
                ),
                422,
            )
        for status in ["draft", "published"]:
            r = self.client.post(
                "/create_course", json={**body, "status": status}, headers=self.headers
            )
            self.assertEqual(r.status_code, 201, r.text)
            self.assertTrue(r.json()["invite_code"])
            read = self.client.get(
                "/get_course_data",
                params={"course_id": r.json()["id"]},
                headers=self.headers,
            )
            self.assertEqual(read.status_code, 200, read.text)
            self.assertNotIn("invite_code", read.json())
            self.assertNotIn("lessons", read.json())

    def test_module_data_retains_only_selected_courses_without_codes(self):
        m = self.module()
        a = self.course(module=m)
        b = self.course(module=m)
        self.member(a)
        r = self.client.get(
            "/get_module_data", params={"module_id": m["id"]}, headers=self.headers
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["id"], str(m["id"]))
        self.assertEqual([d["id"] for d in r.json()["disciplines"]], [str(a["id"])])
        self.assertNotIn("invite_code", r.text)

    def test_member_profiles_have_distinct_user_and_membership_ids(self):
        c = self.course()
        mid = self.member(c)
        r = self.client.get(
            "/get_members", params={"course_id": c["id"]}, headers=self.headers
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsInstance(r.json(), list)
        member = next(m for m in r.json() if m["id"] == str(self.user["id"]))
        self.assertEqual(member["member_id"], str(mid))
        self.assertEqual(member["role"], "student")
        self.assertIsNone(member["team_id"])
        self.assertNotIn("password_hash", r.text)
        self.assertNotIn("is_admin", r.text)

    def test_team_membership_scopes_profiles_and_filters_inactive(self):
        c = self.course()
        team = self.db.execute(
            "INSERT INTO teams(discipline_id,name) VALUES (%s,'Команда') RETURNING id",
            (c["id"],),
        ).fetchone()["id"]
        self.member(c, team=team)
        other = self.create_user()
        self.member(c, other)
        inactive = self.create_user()
        self.member(c, inactive, team, status="left")
        r = self.client.get(
            "/get_team_members", params={"team_id": team}, headers=self.headers
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual([u["id"] for u in r.json()], [str(self.user["id"])])
        h = {"Authorization": "Bearer " + self.token(other["id"])}
        self.assert_error(
            self.client.get("/get_team_members", params={"team_id": team}, headers=h),
            403,
        )
        teacher = {"Authorization": "Bearer " + self.token(self.other["id"])}
        self.assertEqual(
            self.client.get(
                "/get_team_members", params={"team_id": team}, headers=teacher
            ).status_code,
            200,
        )

    def test_assignment_selection_from_colleague_and_target_privacy(self):
        c = self.course()
        mid = self.member(c)
        lid = self.material(c)
        teacher = {"Authorization": "Bearer " + self.token(self.other["id"])}
        r = self.client.post(
            "/create_assignment",
            json={
                "lesson_id": str(lid),
                "title": "Выборочно",
                "description_markdown": "Текст",
                "target_type": "selective",
                "student_ids": [str(self.user["id"])],
            },
            headers=teacher,
        )
        self.assertEqual(r.status_code, 201, r.text)
        aid = r.json()["id"]
        r = self.client.get(
            "/get_assignments", params={"lesson_id": lid}, headers=self.headers
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsInstance(r.json(), list)
        for h in [self.headers, teacher]:
            r = self.client.get(
                "/get_assignment_data", params={"assignment_id": aid}, headers=h
            )
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(len(r.json()["targets"]), 0 if h is self.headers else 1)

    def test_grades_allow_unsubmitted_and_fractional_score(self):
        c = self.course()
        self.member(c)
        lid = self.material(c)
        aid = self.db.execute(
            "INSERT INTO assignments(lesson_id,title,description_markdown) VALUES (%s,'Задание','Текст') RETURNING id",
            (lid,),
        ).fetchone()["id"]
        r = self.client.get(
            "/get_grades", params={"course_id": c["id"]}, headers=self.headers
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsNone(r.json()[0]["submission_id"])
        self.assertIsNone(r.json()[0]["status"])
        self.assertIsNone(r.json()[0]["due_date"])
        self.db.execute(
            "INSERT INTO submissions(assignment_id,submitted_by,status,score) VALUES (%s,%s,'graded',87.5)",
            (aid, self.user["id"]),
        )
        r = self.client.get(
            "/get_grades", params={"course_id": c["id"]}, headers=self.headers
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()[0]["score"], 87.5)
        body = r.json()[0]
        for score in [-1, 101, float("inf")]:
            with self.assertRaises(ValidationError):
                GradeResponse.model_validate({**body, "score": score})

    def test_mock_credentials_cannot_become_admin(self):
        for token in ["dev-token", "mock-owner", "mock-anything"]:
            h = {"Authorization": "Bearer " + token}
            self.assert_error(self.client.get("/auth/sessions", headers=h), 401)
            self.assert_error(
                self.client.patch(
                    "/admin/account_status",
                    params={"user_id": self.other["id"]},
                    json={"blocked": True},
                    headers=h,
                ),
                401,
            )
            self.assert_error(
                self.client.get("/get_file", params={"file_id": uuid4()}, headers=h),
                401,
            )
        self.assertTrue(
            self.db.execute(
                "SELECT is_active FROM users WHERE id=%s", (self.other["id"],)
            ).fetchone()["is_active"]
        )

    def test_openapi_delete_models_invitation_and_frontend(self):
        paths = app.openapi()["paths"]
        for path in [
            "/delete_material",
            "/delete_assignment",
            "/delete_group",
            "/delete_file",
        ]:
            self.assertTrue(
                paths[path]["delete"]["responses"]["200"]["content"][
                    "application/json"
                ]["schema"]["$ref"].endswith("/SuccessResponse")
            )
        self.assertIn("get", paths["/app"])
        self.assertNotIn("post", paths["/app"])
        self.assertTrue(
            paths["/create_invitation"]["post"]["responses"]["201"]["content"][
                "application/json"
            ]["schema"]["$ref"].endswith("/InvitationResponse")
        )

    def test_selective_assignment_rejects_teacher_and_blocked_students(self):
        c = self.course()
        lid = self.material(c)
        self.member(c)
        self.db.execute(
            "UPDATE users SET is_active=false WHERE id=%s", (self.user["id"],)
        )
        teacher = {"Authorization": "Bearer " + self.token(self.other["id"])}
        for uid in [self.other["id"], self.user["id"]]:
            r = self.client.post(
                "/create_assignment",
                json={
                    "lesson_id": str(lid),
                    "title": "Выборочно",
                    "description_markdown": "Текст",
                    "target_type": "selective",
                    "student_ids": [str(uid)],
                },
                headers=teacher,
            )
            self.assert_error(r, 422)
        self.assertEqual(
            self.db.execute(
                "SELECT count(*) AS n FROM assignments WHERE lesson_id=%s", (lid,)
            ).fetchone()["n"],
            0,
        )
