"""Real PostgreSQL integration tests for device sessions and scoped permissions."""

import unittest
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from fastapi.testclient import TestClient
import test_api as fixtures
from backend.api.main import app
from backend.api.security import secret_digest

PASSWORD = fixtures.PASSWORD


class IdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.APIContractTests.setUpClass.__func__(cls)

    create_user = fixtures.APIContractTests.create_user
    token = fixtures.APIContractTests.token
    assert_error = fixtures.APIContractTests.assert_error
    cleanup_rows = fixtures.APIContractTests.cleanup_rows

    def setUp(self):
        fixtures.APIContractTests.setUp(self)
        self.db.execute("DELETE FROM auth_rate_limits")

    def login(self, user=None, client=None):
        r = (client or self.client).post(
            "/auth", json={"email": (user or self.user)["email"], "password": PASSWORD}
        )
        self.assertEqual(r.status_code, 200, r.text)
        return {"Authorization": "Bearer " + r.json()["access_token"]}, r

    def refresh(self, client=None):
        return (client or self.client).post(
            "/auth/refresh", headers={"X-Requested-With": "PocketLMS"}
        )

    def me(self, h, client=None, user=None):
        return (client or self.client).get(
            "/get_user_info", params={"user_id": (user or self.user)["id"]}, headers=h
        )

    def module(self, owner=None):
        return self.db.execute(
            "INSERT INTO modules(title,curator_id) VALUES ('Модуль',%s) RETURNING *",
            ((owner or self.other)["id"],),
        ).fetchone()

    def course(self, owner=None, module=None):
        return self.db.execute(
            "INSERT INTO disciplines(title,author_id,module_id,invite_code,status) VALUES ('Курс',%s,%s,%s,'published') RETURNING *",
            (
                (owner or self.other)["id"],
                module["id"] if module else None,
                uuid4().hex,
            ),
        ).fetchone()

    def invitation(self, h, **body):
        body = {
            k: (
                [str(x) for x in v]
                if isinstance(v, list)
                else str(v)
                if k.endswith("_id")
                else v
            )
            for k, v in body.items()
        }
        return self.client.post("/create_invitation", headers=h, json=body)

    def accept(self, code, h=None):
        return self.client.post(
            "/accept_invitation",
            params={"invite_code": code},
            headers=h or self.headers,
        )

    def staff(self, c, u):
        self.db.execute(
            "INSERT INTO discipline_members(discipline_id,user_id,role) VALUES (%s,%s,'teacher')",
            (c["id"], u["id"]),
        )

    def test_cookie_and_secret_storage(self):
        h, r = self.login()
        cookie = r.headers["set-cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=strict", cookie)
        self.assertEqual(r.headers["cache-control"], "no-store")
        raw = self.client.cookies.get("pocket_lms_refresh")
        row = self.db.execute(
            "SELECT refresh_hash FROM auth_sessions WHERE id=%s",
            (r.json()["session_id"],),
        ).fetchone()
        self.assertEqual(row["refresh_hash"], secret_digest(raw))
        self.assertNotIn(raw, r.text)
        self.assertEqual(self.me(h).status_code, 200)

    def test_two_devices_logout_is_local_and_immediate(self):
        h, _ = self.login()
        with TestClient(app) as second:
            h2, _ = self.login(client=second)
            self.assertEqual(
                self.client.post("/auth/logout", headers=h).status_code, 200
            )
            self.assert_error(self.me(h), 401)
            self.assertEqual(self.me(h2, second).status_code, 200)
            self.assertEqual(self.refresh(second).status_code, 200)
        self.assert_error(self.refresh(), 401)

    def test_rotation_replay_revokes_device(self):
        h, _ = self.login()
        old = self.client.cookies.get("pocket_lms_refresh")
        r = self.refresh()
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotEqual(old, self.client.cookies.get("pocket_lms_refresh"))
        with TestClient(app) as stolen:
            stolen.cookies.set("pocket_lms_refresh", old)
            self.assert_error(self.refresh(stolen), 401)
        self.assert_error(self.me(h), 401)
        self.assert_error(self.refresh(), 401)

    def test_refresh_requires_csrf_header(self):
        self.login()
        self.assert_error(self.client.post("/auth/refresh"), 422)

    def test_concurrent_refresh_cannot_reuse_token(self):
        self.login()
        raw = self.client.cookies.get("pocket_lms_refresh")

        def call(_):
            with TestClient(app) as c:
                c.cookies.set("pocket_lms_refresh", raw)
                return self.refresh(c).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            codes = list(pool.map(call, range(2)))
        self.assertEqual(sorted(codes), [200, 401])

    def test_expired_and_absolute_expiry(self):
        for field in ["expires_at", "absolute_expires_at"]:
            h, r = self.login()
            self.db.execute(
                f"UPDATE auth_sessions SET {field}=now()-interval '1 second' WHERE id=%s",
                (r.json()["session_id"],),
            )
            self.assert_error(self.me(h), 401)
            self.assert_error(self.refresh(), 401)

    def test_change_password_revokes_all_devices(self):
        h, _ = self.login()
        with TestClient(app) as second:
            h2, _ = self.login(client=second)
            body = {
                "current_password": PASSWORD,
                "password": "Changed123",
                "password_confirm": "Changed123",
            }
            self.assertEqual(
                self.client.post(
                    "/auth/change_password", json=body, headers=h
                ).status_code,
                200,
            )
            self.assert_error(self.me(h2, second), 401)
            self.assert_error(self.refresh(second), 401)
        self.assert_error(self.me(h), 401)
        self.assert_error(
            self.client.post(
                "/auth", json={"email": self.user["email"], "password": PASSWORD}
            ),
            401,
        )
        self.assertEqual(
            self.client.post(
                "/auth", json={"email": self.user["email"], "password": "Changed123"}
            ).status_code,
            200,
        )

    def test_password_change_requires_old_password(self):
        body = {
            "current_password": "Wrong123",
            "password": "Changed123",
            "password_confirm": "Changed123",
        }
        self.assert_error(
            self.client.post("/auth/change_password", json=body, headers=self.headers),
            401,
        )
        self.assertEqual(self.me(self.headers).status_code, 200)

    def test_admin_reset_one_time_and_no_email(self):
        self.db.execute(
            "UPDATE users SET is_admin=true WHERE id=%s", (self.other["id"],)
        )
        admin = {"Authorization": "Bearer " + self.token(self.other["id"])}
        self.assert_error(
            self.client.post(
                "/admin/password_reset",
                params={"user_id": self.user["id"]},
                headers=self.headers,
            ),
            403,
        )
        r = self.client.post(
            "/admin/password_reset", params={"user_id": self.user["id"]}, headers=admin
        )
        self.assertEqual(r.status_code, 200, r.text)
        raw = r.json()["reset_code"]
        stored = self.db.execute(
            "SELECT token_hash FROM password_resets WHERE user_id=%s",
            (self.user["id"],),
        ).fetchone()
        self.assertEqual(stored["token_hash"], secret_digest(raw))
        body = {
            "reset_code": raw,
            "password": "ResetPass123",
            "password_confirm": "ResetPass123",
        }
        self.assertEqual(
            self.client.post("/auth/reset_password", json=body).status_code, 200
        )
        self.assert_error(self.client.post("/auth/reset_password", json=body), 400)
        self.assert_error(self.me(self.headers), 401)

    def test_new_reset_invalidates_previous_and_expired_reset_fails(self):
        self.db.execute(
            "UPDATE users SET is_admin=true WHERE id=%s", (self.other["id"],)
        )
        admin = {"Authorization": "Bearer " + self.token(self.other["id"])}

        def issue():
            return self.client.post(
                "/admin/password_reset",
                params={"user_id": self.user["id"]},
                headers=admin,
            ).json()["reset_code"]

        old, new = issue(), issue()
        for code in [old, new]:
            if code == new:
                self.db.execute(
                    "UPDATE password_resets SET expires_at=now()-interval '1 second' WHERE user_id=%s",
                    (self.user["id"],),
                )
            self.assert_error(
                self.client.post(
                    "/auth/reset_password",
                    json={
                        "reset_code": code,
                        "password": "ResetPass123",
                        "password_confirm": "ResetPass123",
                    },
                ),
                400,
            )

    def test_blocking_and_unblocking_never_restore_sessions(self):
        self.db.execute(
            "UPDATE users SET is_admin=true WHERE id=%s", (self.other["id"],)
        )
        admin = {"Authorization": "Bearer " + self.token(self.other["id"])}
        self.assert_error(
            self.client.patch(
                "/admin/account_status",
                params={"user_id": self.other["id"]},
                json={"blocked": True},
                headers=self.headers,
            ),
            403,
        )
        for blocked in [True, False]:
            r = self.client.patch(
                "/admin/account_status",
                params={"user_id": self.user["id"]},
                json={"blocked": blocked},
                headers=admin,
            )
            self.assertEqual(r.status_code, 200, r.text)
            self.assert_error(self.me(self.headers), 401)

    def test_login_throttle_persists_failed_requests(self):
        for n in range(11):
            r = self.client.post(
                "/auth", json={"email": self.user["email"], "password": "Wrong123"}
            )
            self.assertEqual(r.status_code, 401 if n < 10 else 429, r.text)

    def test_creation_is_discoverable_without_manual_membership(self):
        r = self.client.post(
            "/create_module",
            json={"title": "Новый", "curator_id": str(self.user["id"])},
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 201, r.text)
        modules = self.client.get(
            "/get_modules", params={"user_id": self.user["id"]}, headers=self.headers
        ).json()
        self.assertIn(r.json()["id"], [m["id"] for m in modules])
        r = self.client.post(
            "/create_course",
            json={"title": "Новый", "author_id": str(self.user["id"]), "status":"draft"},
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 201, r.text)
        courses = self.client.get(
            "/get_courses", params={"user_id": self.user["id"]}, headers=self.headers
        ).json()
        self.assertEqual(courses[0]["role"], "owner")

    def test_cannot_add_course_to_foreign_module_or_transfer_creator(self):
        m = self.module()
        self.assert_error(
            self.client.post(
                "/create_course",
                json={
                    "title": "Чужой", "status":"draft",
                    "author_id": str(self.user["id"]),
                    "module_id": str(m["id"]),
                },
                headers=self.headers,
            ),
            403,
        )
        m = self.module(self.user)
        self.assert_error(
            self.client.patch(
                "/update_module",
                params={"module_id": m["id"]},
                json={"curator_id": str(self.other["id"])},
                headers=self.headers,
            ),
            403,
        )

    def test_course_teacher_can_invite_into_other_module_course_only(self):
        m = self.module()
        a = self.course(module=m)
        b = self.course(module=m)
        self.staff(a, self.user)
        r = self.invitation(
            self.headers, module_id=m["id"], course_ids=[b["id"]], role="teacher"
        )
        self.assertEqual(r.status_code, 201, r.text)
        outsider = self.create_user()
        h = {"Authorization": "Bearer " + self.token(outsider["id"])}
        self.assert_error(
            self.client.patch(
                "/update_course",
                params={"course_id": b["id"]},
                json={"title": "Нет"},
                headers=h,
            ),
            403,
        )
        self.assertEqual(self.accept(r.json()["invite_code"], h).status_code, 200)
        self.assertEqual(
            self.client.patch(
                "/update_course",
                params={"course_id": b["id"]},
                json={"title": "Да"},
                headers=h,
            ).status_code,
            200,
        )
        self.assert_error(
            self.client.patch(
                "/update_course",
                params={"course_id": a["id"]},
                json={"title": "Нет"},
                headers=h,
            ),
            403,
        )
        self.assert_error(
            self.client.patch(
                "/update_module",
                params={"module_id": m["id"]},
                json={"title": "Нет"},
                headers=h,
            ),
            403,
        )

    def test_student_only_sees_selected_courses(self):
        m = self.module()
        a = self.course(module=m)
        b = self.course(module=m)
        h = {"Authorization": "Bearer " + self.token(self.other["id"])}
        r = self.invitation(h, module_id=m["id"], course_ids=[a["id"]])
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(self.accept(r.json()["invite_code"]).status_code, 200)
        r = self.client.get(
            "/get_module_data", params={"module_id": m["id"]}, headers=self.headers
        )
        self.assertEqual([x["id"] for x in r.json()["disciplines"]], [str(a["id"])])
        self.assert_error(
            self.client.get(
                "/get_course_data", params={"course_id": b["id"]}, headers=self.headers
            ),
            403,
        )

    def test_expired_revoked_capacity_and_idempotent_acceptance(self):
        c = self.course()
        h = {"Authorization": "Bearer " + self.token(self.other["id"])}
        r = self.invitation(h, course_id=c["id"], max_uses=1)
        self.assertEqual(r.status_code, 201, r.text)
        inv = r.json()
        self.assertEqual(self.accept(inv["invite_code"]).status_code, 200)
        self.assertTrue(self.accept(inv["invite_code"]).json()["already_accepted"])
        third = self.create_user()
        third_h = {"Authorization": "Bearer " + self.token(third["id"])}
        self.assert_error(self.accept(inv["invite_code"], third_h), 409)
        self.assertEqual(
            self.client.delete(
                "/revoke_invitation", params={"invitation_id": inv["id"]}, headers=h
            ).status_code,
            200,
        )
        self.assert_error(self.accept(inv["invite_code"]), 404)
        r = self.invitation(h, course_id=c["id"])
        self.db.execute(
            "UPDATE invitations SET expires_at=now()-interval '1 second' WHERE id=%s",
            (r.json()["id"],),
        )
        self.assert_error(self.accept(r.json()["invite_code"]), 404)

    def test_invitation_scope_and_student_permissions(self):
        m = self.module()
        c = self.course()
        h = {"Authorization": "Bearer " + self.token(self.other["id"])}
        self.assert_error(
            self.invitation(h, module_id=m["id"], course_ids=[c["id"]]), 422
        )
        self.assert_error(
            self.invitation(self.headers, course_id=c["id"], role="teacher"), 403
        )

    def test_module_creator_manages_all_courses_but_other_teacher_cannot(self):
        m = self.module()
        c = self.course(self.user, m)
        h = {"Authorization": "Bearer " + self.token(self.other["id"])}
        self.assertEqual(
            self.client.patch(
                "/update_course",
                params={"course_id": c["id"]},
                json={"title": "Да"},
                headers=h,
            ).status_code,
            200,
        )
        third = self.create_user()
        other_course = self.course(third, m)
        self.staff(other_course, self.user)
        third_h = {"Authorization": "Bearer " + self.token(third["id"])}
        self.assert_error(
            self.client.patch(
                "/update_course",
                params={"course_id": c["id"]},
                json={"title": "Нет"},
                headers=third_h,
            ),
            403,
        )
        self.assert_error(
            self.client.patch(
                "/update_module",
                params={"module_id": m["id"]},
                json={"title": "Нет"},
                headers=self.headers,
            ),
            403,
        )

    def test_deletion_only_content_author_or_module_creator(self):
        m = self.module()
        c = self.course(module=m)
        self.staff(c, self.user)
        h = {"Authorization": "Bearer " + self.token(self.other["id"])}
        r = self.client.post(
            "/create_material",
            json={"discipline_id": str(c["id"]), "title": "Материал"},
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 201, r.text)
        lid = r.json()["id"]
        assignment = self.client.post(
            "/create_assignment",
            json={
                "lesson_id": lid,
                "title": "Задание",
                "description_markdown": "Текст",
            },
            headers=h,
        )
        self.assertEqual(assignment.status_code, 201, assignment.text)
        self.assert_error(
            self.client.delete(
                "/delete_assignment",
                params={"assignment_id": assignment.json()["id"]},
                headers=self.headers,
            ),
            403,
        )
        # Cannot bypass child authorship by deleting its parent material.
        self.assert_error(
            self.client.delete(
                "/delete_material", params={"material_id": lid}, headers=self.headers
            ),
            403,
        )
        self.assertEqual(
            self.client.delete(
                "/delete_material", params={"material_id": lid}, headers=h
            ).status_code,
            200,
        )

    def test_removal_hierarchy_and_immutable_creators(self):
        m = self.module()
        a = self.course(module=m)
        b = self.course(module=m)
        self.staff(a, self.user)
        creator = {"Authorization": "Bearer " + self.token(self.other["id"])}
        student = self.create_user()
        student_h = {"Authorization": "Bearer " + self.token(student["id"])}
        r = self.invitation(creator, module_id=m["id"], course_ids=[a["id"], b["id"]])
        self.accept(r.json()["invite_code"], student_h)
        params = {"module_id": m["id"], "member_user_id": student["id"]}
        self.assert_error(
            self.client.delete(
                "/remove_module_member", params=params, headers=self.headers
            ),
            403,
        )
        self.assertEqual(
            self.client.delete(
                "/remove_course_member",
                params={"course_id": a["id"], "member_user_id": student["id"]},
                headers=self.headers,
            ).status_code,
            200,
        )
        self.assert_error(
            self.client.get(
                "/get_course_data", params={"course_id": a["id"]}, headers=student_h
            ),
            403,
        )
        self.assertEqual(
            self.client.get(
                "/get_course_data", params={"course_id": b["id"]}, headers=student_h
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.delete(
                "/remove_module_member", params=params, headers=creator
            ).status_code,
            200,
        )
        self.assert_error(
            self.client.get(
                "/get_module_data", params={"module_id": m["id"]}, headers=student_h
            ),
            403,
        )
        self.assert_error(
            self.client.delete(
                "/remove_course_member",
                params={"course_id": a["id"], "member_user_id": self.other["id"]},
                headers=self.headers,
            ),
            403,
        )

    def test_only_creator_can_revoke_teacher(self):
        m = self.module()
        c = self.course(module=m)
        self.staff(c, self.user)
        third = self.create_user()
        self.staff(c, third)
        params = {"course_id": c["id"], "member_user_id": third["id"]}
        self.assert_error(
            self.client.delete(
                "/remove_course_member", params=params, headers=self.headers
            ),
            403,
        )
        creator = {"Authorization": "Bearer " + self.token(self.other["id"])}
        self.assertEqual(
            self.client.delete(
                "/remove_course_member", params=params, headers=creator
            ).status_code,
            200,
        )

    def test_concurrent_invitation_capacity(self):
        c = self.course()
        creator = {"Authorization": "Bearer " + self.token(self.other["id"])}
        inv = self.invitation(creator, course_id=c["id"], max_uses=1).json()
        third = self.create_user()
        headers = [self.headers, {"Authorization": "Bearer " + self.token(third["id"])}]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda h: self.accept(inv["invite_code"], h).status_code, headers
                )
            )
        self.assertEqual(sorted(results), [200, 409])

    def test_session_inventory_and_no_cross_user_token(self):
        h, r = self.login()
        sessions = self.client.get("/auth/sessions", headers=h)
        self.assertEqual(sessions.status_code, 200, sessions.text)
        self.assertTrue(
            any(
                s["current"] and s["id"] == r.json()["session_id"]
                for s in sessions.json()["items"]
            )
        )
        self.assertNotIn("refresh_hash", sessions.text)
        self.assert_error(
            self.client.get(
                "/get_user_info", params={"user_id": self.other["id"]}, headers=h
            ),
            403,
        )

    def test_old_and_wrong_kind_tokens_cannot_bypass_sessions(self):
        import jwt, os
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        real_session = self.db.execute(
            "SELECT id FROM auth_sessions WHERE user_id=%s LIMIT 1", (self.user["id"],)
        ).fetchone()["id"]
        base = {
            "sub": str(self.user["id"]),
            "iat": now,
            "exp": now + timedelta(minutes=15),
        }
        claims = [
            base,
            {**base, "sid": str(real_session), "type": "refresh"},
            {**base, "sid": str(uuid4()), "type": "access"},
            {
                **base,
                "sid": str(real_session),
                "type": "access",
                "sub": str(self.other["id"]),
            },
        ]
        for data in claims:
            h = {
                "Authorization": "Bearer "
                + jwt.encode(data, os.environ["JWT_SECRET"], algorithm="HS256")
            }
            self.assert_error(self.me(h), 401)

    def test_removed_teacher_outstanding_invitation_cannot_grant_access(self):
        m = self.module()
        a = self.course(module=m)
        self.staff(a, self.user)
        inv = self.invitation(self.headers, course_id=a["id"], role="teacher").json()
        creator = {"Authorization": "Bearer " + self.token(self.other["id"])}
        r = self.client.delete(
            "/remove_course_member",
            params={"course_id": a["id"], "member_user_id": self.user["id"]},
            headers=creator,
        )
        self.assertEqual(r.status_code, 200, r.text)
        third = self.create_user()
        h = {"Authorization": "Bearer " + self.token(third["id"])}
        self.assert_error(self.accept(inv["invite_code"], h), 404)

    def test_student_invitation_never_downgrades_teacher(self):
        c = self.course()
        self.staff(c, self.user)
        creator = {"Authorization": "Bearer " + self.token(self.other["id"])}
        inv = self.invitation(creator, course_id=c["id"]).json()
        self.assertEqual(self.accept(inv["invite_code"]).status_code, 200)
        self.assertEqual(
            self.client.patch(
                "/update_course",
                params={"course_id": c["id"]},
                json={"title": "Преподаватель"},
                headers=self.headers,
            ).status_code,
            200,
        )

    def test_titles_are_validated_and_duplicate_course_is_conflict(self):
        for title in ["", "  ", None]:
            self.assert_error(
                self.client.post(
                    "/create_module",
                    json={"title": title, "curator_id": str(self.user["id"])},
                    headers=self.headers,
                ),
                422,
            )
        course = self.course(self.user)
        self.assert_error(
            self.client.patch(
                "/update_course",
                params={"course_id": course["id"]},
                json={"title": None},
                headers=self.headers,
            ),
            422,
        )
        self.assert_error(
            self.client.post(
                "/create_course",
                json={
                    "title": "Дубль",
                    "author_id": str(self.user["id"]),
                    "invite_code": course["invite_code"],
                },
                headers=self.headers,
            ),
            422,
        )

    def test_standalone_teacher_can_manage_but_cannot_delete_another_authors_content(
        self,
    ):
        c = self.course()
        self.staff(c, self.user)
        creator = {"Authorization": "Bearer " + self.token(self.other["id"])}
        material = self.client.post(
            "/create_material",
            json={"discipline_id": str(c["id"]), "title": "Материал"},
            headers=self.headers,
        )
        self.assertEqual(material.status_code, 201, material.text)
        self.assert_error(
            self.client.delete(
                "/delete_material",
                params={"material_id": material.json()["id"]},
                headers=creator,
            ),
            403,
        )
        self.assertEqual(
            self.client.delete(
                "/delete_material",
                params={"material_id": material.json()["id"]},
                headers=self.headers,
            ).status_code,
            200,
        )

    def test_secure_cookie_configuration(self):
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, AUTH_COOKIE_SECURE="true"):
            _, response = self.login()
            self.assertIn("Secure", response.headers["set-cookie"])

    def test_missing_signing_configuration_does_not_consume_refresh(self):
        import os
        from unittest.mock import patch

        self.login()
        with patch.dict(os.environ, JWT_SECRET=""):
            self.assert_error(self.refresh(), 503)
        self.assertEqual(self.refresh().status_code, 200)

    def test_password_reset_is_single_use_under_concurrency(self):
        self.db.execute(
            "UPDATE users SET is_admin=true WHERE id=%s", (self.other["id"],)
        )
        admin = {"Authorization": "Bearer " + self.token(self.other["id"])}
        raw = self.client.post(
            "/admin/password_reset", params={"user_id": self.user["id"]}, headers=admin
        ).json()["reset_code"]
        body = {
            "reset_code": raw,
            "password": "ResetPass123",
            "password_confirm": "ResetPass123",
        }
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda _: (
                        self.client.post("/auth/reset_password", json=body).status_code
                    ),
                    range(2),
                )
            )
        self.assertEqual(sorted(results), [200, 400])
