"""Scoped invitations and membership changes in a single request transaction."""

from datetime import UTC

from backend.db.identity import event, one


async def module_teacher(conn, module_id, uid):
    row = await one(
        conn,
        """SELECT 1 FROM modules m WHERE m.id=%s AND (m.curator_id=%s OR EXISTS(
        SELECT 1 FROM disciplines d LEFT JOIN discipline_members dm ON dm.discipline_id=d.id
        AND dm.user_id=%s AND dm.status='active' WHERE d.module_id=m.id
        AND (d.author_id=%s OR dm.role IN ('owner','teacher'))))""",
        (module_id, uid, uid, uid),
    )
    return bool(row)


async def module_member(conn, module_id, uid):
    return await one(
        conn,
        "SELECT 1 FROM module_members WHERE module_id=%s AND user_id=%s AND status='active'",
        (module_id, uid),
    )


async def create(conn, actor, digest, module_id, course_ids, role, days, max_uses):
    row = await one(
        conn,
        """INSERT INTO invitations(created_by,token_hash,module_id,role,expires_at,max_uses)
        VALUES (%s,%s,%s,%s,now()+make_interval(days => %s),%s) RETURNING *""",
        (actor, digest, module_id, role, days, max_uses),
    )
    for course_id in course_ids:
        await conn.execute(
            "INSERT INTO invitation_courses VALUES (%s,%s)", (row["id"], course_id)
        )
    await event(conn, actor, "invitation_created", row["id"])
    return row


async def get(conn, invitation_id):
    return await one(conn, "SELECT * FROM invitations WHERE id=%s", (invitation_id,))


async def course_ids(conn, invitation_id):
    return [
        r["discipline_id"]
        for r in await (
            await conn.execute(
                "SELECT discipline_id FROM invitation_courses WHERE invitation_id=%s ORDER BY discipline_id",
                (invitation_id,),
            )
        ).fetchall()
    ]


async def accept(conn, digest, uid):
    # Serializes capacity accounting and concurrent acceptance of the same invitation.
    inv = await one(
        conn, "SELECT * FROM invitations WHERE token_hash=%s FOR UPDATE", (digest,)
    )
    if not inv:
        return None, "invalid"
    from datetime import datetime

    if inv["revoked_at"] or inv["expires_at"] <= datetime.now(UTC):
        return None, "invalid"
    previous = await one(
        conn,
        "SELECT 1 FROM invitation_acceptances WHERE invitation_id=%s AND user_id=%s",
        (inv["id"], uid),
    )
    if previous:
        return {
            "invitation_id": inv["id"],
            "module_id": inv["module_id"],
            "course_ids": await course_ids(conn, inv["id"]),
            "role": inv["role"],
            "already_accepted": True,
        }, None
    if inv["uses"] >= inv["max_uses"]:
        return None, "full"
    ids = await course_ids(conn, inv["id"])
    if not ids:
        return None, "invalid"
    inviter = await one(
        conn,
        "SELECT id,is_admin FROM users WHERE id=%s AND is_active",
        (inv["created_by"],),
    )
    if not inviter:
        return None, "invalid"
    if not inviter["is_admin"]:
        # Removing a teacher also removes authority from their outstanding invitations.
        for cid in ids:
            course = await one(conn, "SELECT * FROM disciplines WHERE id=%s", (cid,))
            if course["module_id"]:
                allowed = await module_teacher(
                    conn, course["module_id"], inv["created_by"]
                )
            else:
                allowed = course["author_id"] == inv["created_by"] or bool(
                    await one(
                        conn,
                        "SELECT 1 FROM discipline_members WHERE discipline_id=%s AND user_id=%s AND status='active' AND role IN ('teacher','owner')",
                        (cid, inv["created_by"]),
                    )
                )
            if not allowed:
                return None, "invalid"
    for cid in ids:
        # Existing teacher/creator rights can never be downgraded through a student invite.
        await conn.execute(
            """INSERT INTO discipline_members(discipline_id,user_id,role,status)
            VALUES (%s,%s,%s,'active') ON CONFLICT(discipline_id,user_id) DO UPDATE SET
            role=CASE WHEN discipline_members.role='owner' THEN 'owner'
                 WHEN discipline_members.status='active' AND discipline_members.role='teacher' THEN 'teacher'
                 ELSE EXCLUDED.role END, status='active', team_id=CASE WHEN discipline_members.status='active' THEN discipline_members.team_id ELSE NULL END""",
            (cid, uid, inv["role"]),
        )
    if inv["module_id"]:
        await conn.execute(
            """INSERT INTO module_members(module_id,user_id) VALUES (%s,%s)
            ON CONFLICT(module_id,user_id) DO UPDATE SET status='active'""",
            (inv["module_id"], uid),
        )
    await conn.execute(
        "INSERT INTO invitation_acceptances(invitation_id,user_id) VALUES (%s,%s)",
        (inv["id"], uid),
    )
    await conn.execute("UPDATE invitations SET uses=uses+1 WHERE id=%s", (inv["id"],))
    await event(conn, uid, "invitation_accepted", inv["id"])
    return {
        "invitation_id": inv["id"],
        "module_id": inv["module_id"],
        "course_ids": ids,
        "role": inv["role"],
        "already_accepted": False,
    }, None


async def revoke(conn, invitation_id, actor):
    await conn.execute(
        "UPDATE invitations SET revoked_at=now() WHERE id=%s", (invitation_id,)
    )
    await event(conn, actor, "invitation_revoked", invitation_id)


async def remove_course_member(conn, cid, uid, actor):
    await conn.execute(
        "UPDATE discipline_members SET status='left',team_id=NULL WHERE discipline_id=%s AND user_id=%s",
        (cid, uid),
    )
    await event(conn, actor, "course_member_removed", uid)


async def remove_module_member(conn, mid, uid, actor):
    await conn.execute(
        "UPDATE module_members SET status='left' WHERE module_id=%s AND user_id=%s",
        (mid, uid),
    )
    await conn.execute(
        """UPDATE discipline_members SET status='left',team_id=NULL WHERE user_id=%s
        AND discipline_id IN (SELECT id FROM disciplines WHERE module_id=%s)""",
        (uid, mid),
    )
    await event(conn, actor, "module_member_removed", uid)
