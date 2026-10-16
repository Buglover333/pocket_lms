from uuid import UUID
import psycopg
from psycopg import sql
from psycopg.rows import dict_row

try:
    from backend.schemas.data import (
        DisciplineCreate,
        DisciplineUpdate,
        ModuleCreate,
        ModuleUpdate,
    )
except (ImportError, ValueError):
    from ..schemas.data import (
        DisciplineCreate,
        DisciplineUpdate,
        ModuleCreate,
        ModuleUpdate,
    )


# ==============================================================================
# ПОЛЬЗОВАТЕЛИ
# ==============================================================================

async def get_user_by_id(conn: psycopg.AsyncConnection, user_id: UUID) -> dict | None:
    """Возвращает пользователя по ID."""
    query = "SELECT * FROM users WHERE id = %s;"
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (user_id,))
        return await cur.fetchone()


# ==============================================================================
# 1. МЕТОДЫ ДЛЯ МОДУЛЕЙ (Таблица modules)
# ==============================================================================

async def create_module(conn: psycopg.AsyncConnection, data: ModuleCreate) -> dict:
    """Создает новый образовательный модуль."""
    query = """
        INSERT INTO modules (title, description, curator_id)
        VALUES (%s, %s, %s)
        RETURNING *;
    """
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (data.title, data.description, data.curator_id))
        return await cur.fetchone()


async def get_module_by_id(conn: psycopg.AsyncConnection, module_id: UUID) -> dict | None:
    """Возвращает модуль по его ID."""
    query = "SELECT * FROM modules WHERE id = %s;"
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (module_id,))
        return await cur.fetchone()


async def get_modules_list(
    conn: psycopg.AsyncConnection,
    limit: int = 100,
    offset: int = 0
) -> list[dict]:
    """Возвращает список образовательных модулей с пагинацией."""
    query = "SELECT * FROM modules ORDER BY created_at DESC LIMIT %s OFFSET %s;"
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (limit, offset))
        return await cur.fetchall()


async def update_module(
    conn: psycopg.AsyncConnection,
    module_id: UUID,
    data: ModuleUpdate
) -> dict | None:
    """Обновляет только переданные поля модуля."""
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return await get_module_by_id(conn, module_id)

    set_clauses = [
        sql.SQL("{} = %s").format(sql.Identifier(col))
        for col in update_data.keys()
    ]
    set_clauses.append(sql.SQL("updated_at = now()"))

    query = sql.SQL("UPDATE modules SET {} WHERE id = %s RETURNING *;").format(
        sql.SQL(", ").join(set_clauses)
    )
    values = list(update_data.values()) + [module_id]

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, values)
        return await cur.fetchone()


async def delete_module(conn: psycopg.AsyncConnection, module_id: UUID) -> bool:
    """Удаляет модуль по ID. Возвращает True, если строка была удалена."""
    query = "DELETE FROM modules WHERE id = %s;"
    async with conn.cursor() as cur:
        await cur.execute(query, (module_id,))
        return cur.rowcount > 0


# ==============================================================================
# 2. МЕТОДЫ ДЛЯ ДИСЦИПЛИН / КУРСОВ (Таблица disciplines)
# ==============================================================================

async def create_discipline(conn: psycopg.AsyncConnection, data: DisciplineCreate) -> dict:
    """Создает новый курс/дисциплину."""
    query = """
        INSERT INTO disciplines (
            module_id, author_id, title, discipline_type,
            status, description, invite_code, cover_file_id, ends_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *;
    """
    values = (
        data.module_id,
        data.author_id,
        data.title,
        data.discipline_type,
        data.status,
        data.description,
        data.invite_code,
        data.cover_file_id,
        data.ends_at,
    )
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, values)
        return await cur.fetchone()


async def get_discipline_by_id(conn: psycopg.AsyncConnection, discipline_id: UUID) -> dict | None:
    """Возвращает курс по ID."""
    query = "SELECT * FROM disciplines WHERE id = %s;"
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (discipline_id,))
        return await cur.fetchone()


async def get_discipline_by_invite_code(conn: psycopg.AsyncConnection, invite_code: str) -> dict | None:
    """Находит курс по коду приглашения (для записи студентов)."""
    query = "SELECT * FROM disciplines WHERE invite_code = %s;"
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (invite_code,))
        return await cur.fetchone()


async def get_disciplines_by_module(conn: psycopg.AsyncConnection, module_id: UUID) -> list[dict]:
    """Возвращает список курсов, привязанных к конкретному модулю."""
    query = "SELECT * FROM disciplines WHERE module_id = %s ORDER BY created_at DESC;"
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (module_id,))
        return await cur.fetchall()


async def get_disciplines_list(
    conn: psycopg.AsyncConnection,
    limit: int = 100,
    offset: int = 0
) -> list[dict]:
    """Возвращает список всех курсов с пагинацией."""
    query = "SELECT * FROM disciplines ORDER BY created_at DESC LIMIT %s OFFSET %s;"
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (limit, offset))
        return await cur.fetchall()


async def update_discipline(
    conn: psycopg.AsyncConnection,
    discipline_id: UUID,
    data: DisciplineUpdate
) -> dict | None:
    """Обновляет только переданные поля курса."""
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return await get_discipline_by_id(conn, discipline_id)

    set_clauses = [
        sql.SQL("{} = %s").format(sql.Identifier(col))
        for col in update_data.keys()
    ]
    set_clauses.append(sql.SQL("updated_at = now()"))

    query = sql.SQL("UPDATE disciplines SET {} WHERE id = %s RETURNING *;").format(
        sql.SQL(", ").join(set_clauses)
    )
    values = list(update_data.values()) + [discipline_id]

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, values)
        return await cur.fetchone()


async def delete_discipline(conn: psycopg.AsyncConnection, discipline_id: UUID) -> bool:
    """Удаляет курс по ID. Возвращает True, если запись была удалена."""
    query = "DELETE FROM disciplines WHERE id = %s;"
    async with conn.cursor() as cur:
        await cur.execute(query, (discipline_id,))
        return cur.rowcount > 0
