from typing import Any
from uuid import UUID

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

try:
    from backend.schemas.data import UserCreate, UserUpdate
except ImportError:  # Allows importing from src.backend as well.
    from ..schemas.data import UserCreate, UserUpdate


async def create_user(conn: psycopg.AsyncConnection, user: UserCreate) -> dict[str, Any]:
    """Create a user. The caller must pass a password hash, never a raw password."""
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            INSERT INTO users (email, password_hash, first_name, last_name)
            VALUES (%s, %s, %s, %s)
            RETURNING id, email, first_name, last_name, is_active, created_at, updated_at
            """,
            (user.email, user.password_hash, user.first_name, user.last_name),
        )
        return await cur.fetchone()


async def get_user_by_id(
    conn: psycopg.AsyncConnection, user_id: UUID, *, include_inactive: bool = False
) -> dict[str, Any] | None:
    query = "SELECT id, email, first_name, last_name, is_active, created_at, updated_at FROM users WHERE id = %s"
    if not include_inactive:
        query += " AND is_active = TRUE"
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (user_id,))
        return await cur.fetchone()


async def get_users(
    conn: psycopg.AsyncConnection, *, include_inactive: bool = False, limit: int = 100, offset: int = 0
) -> list[dict[str, Any]]:
    query = "SELECT id, email, first_name, last_name, is_active, created_at, updated_at FROM users"
    if not include_inactive:
        query += " WHERE is_active = TRUE"
    query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (limit, offset))
        return await cur.fetchall()


async def update_user(
    conn: psycopg.AsyncConnection, user_id: UUID, user: UserUpdate
) -> dict[str, Any] | None:
    changes = user.model_dump(exclude_unset=True)
    if not changes:
        return await get_user_by_id(conn, user_id, include_inactive=True)

    allowed_columns = {"email", "password_hash", "first_name", "last_name"}
    if not set(changes).issubset(allowed_columns):
        raise ValueError("UserUpdate contains unsupported fields")

    assignments = [
        sql.SQL("{} = %s").format(sql.Identifier(column)) for column in changes
    ]
    assignments.append(sql.SQL("updated_at = CURRENT_TIMESTAMP"))
    query = sql.SQL(
        "UPDATE users SET {} WHERE id = %s AND is_active = TRUE "
        "RETURNING id, email, first_name, last_name, is_active, created_at, updated_at"
    ).format(sql.SQL(", ").join(assignments))
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (*changes.values(), user_id))
        return await cur.fetchone()


async def delete_user(conn: psycopg.AsyncConnection, user_id: UUID) -> bool:
    """Soft-delete a user by setting is_active to FALSE."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE users
            SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND is_active = TRUE
            """,
            (user_id,),
        )
        return cur.rowcount > 0
