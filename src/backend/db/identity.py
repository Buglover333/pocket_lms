"""Identity persistence. Secrets are hashed; security failures survive request rollback."""

from datetime import UTC, datetime

from backend.db.connection import connection


async def one(conn, query, params=()):
    return await (await conn.execute(query, params)).fetchone()


async def event(conn, actor, action, subject=None):
    await conn.execute(
        "INSERT INTO security_events(actor_id,action,subject_id) VALUES (%s,%s,%s)",
        (actor, action, subject),
    )


async def rate_limit(key, limit, seconds=900):
    # Separate short transaction: a rejected HTTP request must not undo its counter.
    async with connection() as conn:
        row = await one(
            conn,
            """INSERT INTO auth_rate_limits(key,attempts,expires_at)
            VALUES (%s,1,now()+make_interval(secs => %s))
            ON CONFLICT(key) DO UPDATE SET
            attempts=CASE WHEN auth_rate_limits.expires_at<=now() THEN 1 ELSE auth_rate_limits.attempts+1 END,
            expires_at=CASE WHEN auth_rate_limits.expires_at<=now() THEN EXCLUDED.expires_at ELSE auth_rate_limits.expires_at END
            RETURNING attempts""",
            (key, seconds),
        )
        return row["attempts"] <= limit


async def create_session(conn, uid, digest, name):
    # Serialize against password changes and blocking.
    user = await one(
        conn, "SELECT id FROM users WHERE id=%s AND is_active FOR UPDATE", (uid,)
    )
    if not user:
        return None
    return await one(
        conn,
        "INSERT INTO auth_sessions(user_id,refresh_hash,device_name) VALUES (%s,%s,%s) RETURNING *",
        (uid, digest, name),
    )


async def session_user(conn, sid, uid):
    return await one(
        conn,
        """SELECT id FROM auth_sessions WHERE id=%s AND user_id=%s
        AND revoked_at IS NULL AND expires_at>now() AND absolute_expires_at>now()""",
        (sid, uid),
    )


async def rotate_refresh(old_hash, new_hash):
    # All rotation / replay actions commit even if the HTTP layer returns 401.
    async with connection() as conn:
        found = await one(
            conn,
            """SELECT user_id,id FROM auth_sessions WHERE refresh_hash=%s
            UNION ALL SELECT s.user_id,s.id FROM used_refresh_tokens t JOIN auth_sessions s ON s.id=t.session_id WHERE t.token_hash=%s""",
            (old_hash, old_hash),
        )
        if not found:
            return None
        user = await one(
            conn,
            "SELECT id FROM users WHERE id=%s AND is_active FOR UPDATE",
            (found["user_id"],),
        )
        if not user:
            return None
        session = await one(
            conn, "SELECT * FROM auth_sessions WHERE id=%s FOR UPDATE", (found["id"],)
        )
        if session["refresh_hash"] != old_hash:
            await conn.execute(
                "UPDATE auth_sessions SET revoked_at=now() WHERE id=%s",
                (session["id"],),
            )
            await event(conn, session["user_id"], "refresh_replay", session["id"])
            return None
        now = datetime.now(UTC)
        if (
            session["revoked_at"]
            or min(session["expires_at"], session["absolute_expires_at"]) <= now
        ):
            return None
        await conn.execute(
            "INSERT INTO used_refresh_tokens(token_hash,session_id) VALUES (%s,%s)",
            (old_hash, session["id"]),
        )
        return await one(
            conn,
            """UPDATE auth_sessions SET refresh_hash=%s,last_used_at=now(),
            expires_at=LEAST(now()+interval '90 days',absolute_expires_at) WHERE id=%s RETURNING *""",
            (new_hash, session["id"]),
        )


async def revoke_session(conn, sid, uid):
    await conn.execute(
        "UPDATE auth_sessions SET revoked_at=now() WHERE id=%s AND user_id=%s",
        (sid, uid),
    )
    await event(conn, uid, "logout", sid)


async def sessions(conn, uid):
    return await (
        await conn.execute(
            """SELECT id,device_name,created_at,last_used_at,expires_at FROM auth_sessions
        WHERE user_id=%s AND revoked_at IS NULL AND expires_at>now() AND absolute_expires_at>now() ORDER BY created_at""",
            (uid,),
        )
    ).fetchall()


async def credentials_for_update(conn, email):
    return await one(
        conn,
        "SELECT id,password_hash FROM users WHERE lower(email)=lower(%s) AND is_active FOR UPDATE",
        (email,),
    )


async def replace_password(conn, uid, digest):
    await conn.execute(
        "UPDATE users SET password_hash=%s,updated_at=now() WHERE id=%s", (digest, uid)
    )
    await conn.execute(
        "UPDATE auth_sessions SET revoked_at=now() WHERE user_id=%s AND revoked_at IS NULL",
        (uid,),
    )
    await conn.execute(
        "UPDATE password_resets SET consumed_at=now() WHERE user_id=%s AND consumed_at IS NULL",
        (uid,),
    )
    await event(conn, uid, "password_changed", uid)


async def issue_reset(conn, uid, digest, actor):
    user = await one(
        conn, "SELECT id FROM users WHERE id=%s AND is_active FOR UPDATE", (uid,)
    )
    if not user:
        return None
    await conn.execute(
        "UPDATE password_resets SET consumed_at=now() WHERE user_id=%s AND consumed_at IS NULL",
        (uid,),
    )
    row = await one(
        conn,
        "INSERT INTO password_resets(user_id,token_hash,issued_by) VALUES (%s,%s,%s) RETURNING expires_at",
        (uid, digest, actor),
    )
    await event(conn, actor, "reset_issued", uid)
    return row


async def reset_password(conn, digest, new_password_hash):
    reset = await one(
        conn, "SELECT user_id FROM password_resets WHERE token_hash=%s", (digest,)
    )
    if not reset:
        return False
    user = await one(
        conn,
        "SELECT id FROM users WHERE id=%s AND is_active FOR UPDATE",
        (reset["user_id"],),
    )
    if not user:
        return False
    reset = await one(
        conn,
        "SELECT * FROM password_resets WHERE token_hash=%s AND consumed_at IS NULL AND expires_at>now() FOR UPDATE",
        (digest,),
    )
    if not reset:
        return False
    await replace_password(conn, reset["user_id"], new_password_hash)
    return True


async def set_blocked(conn, uid, blocked, actor):
    row = await one(
        conn,
        "UPDATE users SET is_active=%s,updated_at=now() WHERE id=%s RETURNING id,is_active",
        (not blocked, uid),
    )
    if row and blocked:
        await conn.execute(
            "UPDATE auth_sessions SET revoked_at=now() WHERE user_id=%s", (uid,)
        )
        await conn.execute(
            "UPDATE password_resets SET consumed_at=now() WHERE user_id=%s", (uid,)
        )
    if row:
        await event(
            conn, actor, "account_blocked" if blocked else "account_unblocked", uid
        )
    return row


async def lock_user(conn, uid):
    return await one(conn, "SELECT id FROM users WHERE id=%s FOR UPDATE", (uid,))
