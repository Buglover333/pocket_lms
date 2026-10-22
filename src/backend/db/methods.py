import json
from typing import Any
from uuid import UUID

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

try:
    from backend.schemas.data import (
        AssignmentCreateRequest,
        AssignmentTargetCreateRequest,
        AssignmentUpdateRequest,
        DisciplineCreateRequest,
        DisciplineMemberCreateRequest,
        DisciplineMemberUpdateRequest,
        DisciplineUpdateRequest,
        FileCreateRequest,
        LessonCreateRequest,
        LessonUpdateRequest,
        ModuleCreateRequest,
        ModuleUpdateRequest,
        SubmissionCreateRequest,
        SubmissionReviewRequest,
        SubmissionUpdateRequest,
        TeamCreateRequest,
        TeamUpdateRequest,
        UserCreate,
        UserUpdate,
    )
except (ImportError, ValueError):
    from ..schemas.data import (
        AssignmentCreateRequest,
        AssignmentTargetCreateRequest,
        AssignmentUpdateRequest,
        DisciplineCreateRequest,
        DisciplineMemberCreateRequest,
        DisciplineMemberUpdateRequest,
        DisciplineUpdateRequest,
        FileCreateRequest,
        LessonCreateRequest,
        LessonUpdateRequest,
        ModuleCreateRequest,
        ModuleUpdateRequest,
        SubmissionCreateRequest,
        SubmissionReviewRequest,
        SubmissionUpdateRequest,
        TeamCreateRequest,
        TeamUpdateRequest,
        UserCreate,
        UserUpdate,
    )


# ==============================================================================
# 1. ПОЛЬЗОВАТЕЛИ (Таблица users)
# ==============================================================================

async def create_user(conn: psycopg.AsyncConnection, user: UserCreate) -> dict[str, Any]:
    """Создать пользователя. Сохраняется безопасный хэш пароля."""
    query = """
        INSERT INTO users (email, password_hash, first_name, last_name)
        VALUES (%s, %s, %s, %s)
        RETURNING id, email, first_name, last_name, is_active, created_at, updated_at;
    """
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (user.email, user.password_hash, user.first_name, user.last_name))
        return await cur.fetchone()


async def get_user_by_id(
    conn: psycopg.AsyncConnection, user_id: UUID, *, include_inactive: bool = False
) -> dict[str, Any] | None:
    """Получить пользователя по ID."""
    query = "SELECT id, email, first_name, last_name, is_active, created_at, updated_at FROM users WHERE id = %s"
    if not include_inactive:
        query += " AND is_active = TRUE"
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (user_id,))
        return await cur.fetchone()


async def get_users(
    conn: psycopg.AsyncConnection, *, include_inactive: bool = False, limit: int = 100, offset: int = 0
) -> list[dict[str, Any]]:
    """Список пользователей с пагинацией."""
    query = "SELECT id, email, first_name, last_name, is_active, created_at, updated_at FROM users"
    if not include_inactive:
        query += " WHERE is_active = TRUE"
    query += " ORDER BY created_at DESC LIMIT %s OFFSET %s;"
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (limit, offset))
        return await cur.fetchall()


async def update_user(
    conn: psycopg.AsyncConnection, user_id: UUID, user: UserUpdate
) -> dict[str, Any] | None:
    """Обновление данных пользователя."""
    changes = user.model_dump(exclude_unset=True)
    if not changes:
        return await get_user_by_id(conn, user_id, include_inactive=True)

    allowed_columns = {"email", "password_hash", "first_name", "last_name"}
    if not set(changes).issubset(allowed_columns):
        raise ValueError("UserUpdate содержит неподдерживаемые поля")

    assignments = [sql.SQL("{} = %s").format(sql.Identifier(column)) for column in changes]
    assignments.append(sql.SQL("updated_at = CURRENT_TIMESTAMP"))
    query = sql.SQL(
        "UPDATE users SET {} WHERE id = %s AND is_active = TRUE "
        "RETURNING id, email, first_name, last_name, is_active, created_at, updated_at;"
    ).format(sql.SQL(", ").join(assignments))
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (*changes.values(), user_id))
        return await cur.fetchone()


async def delete_user(conn: psycopg.AsyncConnection, user_id: UUID) -> bool:
    """Мягкое удаление пользователя (soft delete через is_active = FALSE)."""
    query = """
        UPDATE users
        SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s AND is_active = TRUE;
    """
    async with conn.cursor() as cur:
        await cur.execute(query, (user_id,))
        return cur.rowcount > 0


# ==============================================================================
# 2. МОДУЛИ (Таблица modules)
# ==============================================================================

async def create_module(conn: psycopg.AsyncConnection, data: ModuleCreateRequest) -> dict:
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
    data: ModuleUpdateRequest
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
# 3. ДИСЦИПЛИНЫ / КУРСЫ (Таблица disciplines)
# ==============================================================================

async def create_discipline(conn: psycopg.AsyncConnection, data: DisciplineCreateRequest) -> dict:
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
    data: DisciplineUpdateRequest
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


# ==============================================================================
# 4. КОМАНДЫ (Таблица teams)
# ==============================================================================

async def create_team(conn: psycopg.AsyncConnection, data: TeamCreateRequest) -> dict:
    """Создать команду внутри курса."""
    query = """
        INSERT INTO teams (discipline_id, name, description)
        VALUES (%s, %s, %s)
        RETURNING *;
    """
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (data.discipline_id, data.name, data.description))
        return await cur.fetchone()


async def get_team_by_id(conn: psycopg.AsyncConnection, team_id: UUID) -> dict | None:
    """Получить команду по ID."""
    query = "SELECT * FROM teams WHERE id = %s;"
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (team_id,))
        return await cur.fetchone()


async def get_teams_by_discipline(conn: psycopg.AsyncConnection, discipline_id: UUID) -> list[dict]:
    """Список всех команд конкретного курса."""
    query = "SELECT * FROM teams WHERE discipline_id = %s ORDER BY created_at ASC;"
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (discipline_id,))
        return await cur.fetchall()


async def get_team_members(conn: psycopg.AsyncConnection, team_id: UUID) -> list[dict]:
    """Получить список участников команды со сведениями о студентах (для командного оценивания)."""
    query = """
        SELECT dm.id AS member_id, dm.user_id, dm.role, dm.status,
               u.email, u.first_name, u.last_name
        FROM discipline_members dm
        JOIN users u ON dm.user_id = u.id
        WHERE dm.team_id = %s
        ORDER BY u.last_name, u.first_name;
    """
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (team_id,))
        return await cur.fetchall()


async def update_team(conn: psycopg.AsyncConnection, team_id: UUID, data: TeamUpdateRequest) -> dict | None:
    """Обновить название или описание команды."""
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return await get_team_by_id(conn, team_id)

    set_clauses = [sql.SQL("{} = %s").format(sql.Identifier(col)) for col in update_data.keys()]
    query = sql.SQL("UPDATE teams SET {} WHERE id = %s RETURNING *;").format(sql.SQL(", ").join(set_clauses))
    values = list(update_data.values()) + [team_id]

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, values)
        return await cur.fetchone()


async def delete_team(conn: psycopg.AsyncConnection, team_id: UUID) -> bool:
    """Удалить команду."""
    query = "DELETE FROM teams WHERE id = %s;"
    async with conn.cursor() as cur:
        await cur.execute(query, (team_id,))
        return cur.rowcount > 0


# ==============================================================================
# 5. УЧАСТНИКИ КУРСА (Таблица discipline_members)
# ==============================================================================

async def add_discipline_member(conn: psycopg.AsyncConnection, data: DisciplineMemberCreateRequest) -> dict:
    """Записать пользователя (студента/преподавателя) на курс."""
    query = """
        INSERT INTO discipline_members (discipline_id, user_id, role, status, team_id)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *;
    """
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (data.discipline_id, data.user_id, data.role, data.status, data.team_id))
        return await cur.fetchone()


async def get_discipline_member_by_id(conn: psycopg.AsyncConnection, member_id: UUID) -> dict | None:
    """Получить запись участника по ID."""
    query = "SELECT * FROM discipline_members WHERE id = %s;"
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (member_id,))
        return await cur.fetchone()


async def get_discipline_members(
    conn: psycopg.AsyncConnection, discipline_id: UUID, role: str | None = None
) -> list[dict]:
    """Список участников курса с опциональной фильтрацией по роли."""
    query = "SELECT * FROM discipline_members WHERE discipline_id = %s"
    params: list[Any] = [discipline_id]
    if role:
        query += " AND role = %s"
        params.append(role)
    query += " ORDER BY enrolled_at ASC;"

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, params)
        return await cur.fetchall()


async def get_discipline_members_with_profiles(
    conn: psycopg.AsyncConnection, discipline_id: UUID
) -> list[dict]:
    """Список участников с контактными данными из users (для раздела Контакты)."""
    query = """
        SELECT dm.id, dm.discipline_id, dm.user_id, dm.role, dm.status, dm.team_id, dm.enrolled_at,
               u.email, u.first_name, u.last_name, u.avatar_id
        FROM discipline_members dm
        JOIN users u ON dm.user_id = u.id
        WHERE dm.discipline_id = %s
        ORDER BY dm.role, u.last_name, u.first_name;
    """
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (discipline_id,))
        return await cur.fetchall()


async def get_user_disciplines(conn: psycopg.AsyncConnection, user_id: UUID) -> list[dict]:
    """Список всех курсов, в которых состоит пользователь."""
    query = """
        SELECT d.*, dm.role AS member_role, dm.status AS member_status, dm.team_id
        FROM discipline_members dm
        JOIN disciplines d ON dm.discipline_id = d.id
        WHERE dm.user_id = %s
        ORDER BY dm.enrolled_at DESC;
    """
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (user_id,))
        return await cur.fetchall()


async def update_discipline_member(
    conn: psycopg.AsyncConnection, member_id: UUID, data: DisciplineMemberUpdateRequest
) -> dict | None:
    """Изменить роль, статус или команду участника."""
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return await get_discipline_member_by_id(conn, member_id)

    set_clauses = [sql.SQL("{} = %s").format(sql.Identifier(col)) for col in update_data.keys()]
    query = sql.SQL("UPDATE discipline_members SET {} WHERE id = %s RETURNING *;").format(
        sql.SQL(", ").join(set_clauses)
    )
    values = list(update_data.values()) + [member_id]

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, values)
        return await cur.fetchone()


async def remove_discipline_member(conn: psycopg.AsyncConnection, member_id: UUID) -> bool:
    """Исключить участника с курса."""
    query = "DELETE FROM discipline_members WHERE id = %s;"
    async with conn.cursor() as cur:
        await cur.execute(query, (member_id,))
        return cur.rowcount > 0


# ==============================================================================
# 6. УРОКИ (Таблица lessons)
# ==============================================================================

async def create_lesson(conn: psycopg.AsyncConnection, data: LessonCreateRequest) -> dict:
    """Создать урок в курсе."""
    query = """
        INSERT INTO lessons (discipline_id, title, order_index, content_markdown, is_published)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *;
    """
    values = (data.discipline_id, data.title, data.order_index, data.content_markdown, data.is_published)
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, values)
        return await cur.fetchone()


async def get_lesson_by_id(conn: psycopg.AsyncConnection, lesson_id: UUID) -> dict | None:
    """Получить урок по ID."""
    query = "SELECT * FROM lessons WHERE id = %s;"
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (lesson_id,))
        return await cur.fetchone()


async def get_lessons_by_discipline(
    conn: psycopg.AsyncConnection, discipline_id: UUID, only_published: bool = False
) -> list[dict]:
    """Список уроков курса в порядке очередности."""
    query = "SELECT * FROM lessons WHERE discipline_id = %s"
    if only_published:
        query += " AND is_published = TRUE"
    query += " ORDER BY order_index ASC;"

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (discipline_id,))
        return await cur.fetchall()


async def update_lesson(conn: psycopg.AsyncConnection, lesson_id: UUID, data: LessonUpdateRequest) -> dict | None:
    """Обновить урок."""
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return await get_lesson_by_id(conn, lesson_id)

    set_clauses = [sql.SQL("{} = %s").format(sql.Identifier(col)) for col in update_data.keys()]
    set_clauses.append(sql.SQL("updated_at = now()"))
    query = sql.SQL("UPDATE lessons SET {} WHERE id = %s RETURNING *;").format(sql.SQL(", ").join(set_clauses))
    values = list(update_data.values()) + [lesson_id]

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, values)
        return await cur.fetchone()


async def delete_lesson(conn: psycopg.AsyncConnection, lesson_id: UUID) -> bool:
    """Удалить урок."""
    query = "DELETE FROM lessons WHERE id = %s;"
    async with conn.cursor() as cur:
        await cur.execute(query, (lesson_id,))
        return cur.rowcount > 0


# ==============================================================================
# 7. ЗАДАНИЯ (Таблица assignments)
# ==============================================================================

async def create_assignment(conn: psycopg.AsyncConnection, data: AssignmentCreateRequest) -> dict:
    """Создать задание к уроку."""
    query = """
        INSERT INTO assignments (
            lesson_id, title, description_markdown, target_type,
            is_team_work, max_score, due_date, template_file_id, is_published
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *;
    """
    values = (
        data.lesson_id, data.title, data.description_markdown, data.target_type,
        data.is_team_work, data.max_score, data.due_date, data.template_file_id, data.is_published
    )
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, values)
        return await cur.fetchone()


async def get_assignment_by_id(conn: psycopg.AsyncConnection, assignment_id: UUID) -> dict | None:
    """Получить задание по ID."""
    query = "SELECT * FROM assignments WHERE id = %s;"
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (assignment_id,))
        return await cur.fetchone()


async def get_assignments_by_lesson(conn: psycopg.AsyncConnection, lesson_id: UUID) -> list[dict]:
    """Получить все задания урока."""
    query = "SELECT * FROM assignments WHERE lesson_id = %s ORDER BY created_at ASC;"
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (lesson_id,))
        return await cur.fetchall()


async def get_discipline_deadlines(conn: psycopg.AsyncConnection, discipline_id: UUID) -> list[dict]:
    """Задания с дедлайнами для отображения в Календаре."""
    query = """
        SELECT a.id, a.lesson_id, a.title, a.due_date, a.max_score, a.is_team_work, l.title AS lesson_title
        FROM assignments a
        JOIN lessons l ON a.lesson_id = l.id
        WHERE l.discipline_id = %s AND a.due_date IS NOT NULL AND a.is_published = TRUE
        ORDER BY a.due_date ASC;
    """
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (discipline_id,))
        return await cur.fetchall()


async def update_assignment(
    conn: psycopg.AsyncConnection, assignment_id: UUID, data: AssignmentUpdateRequest
) -> dict | None:
    """Обновить параметры задания."""
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return await get_assignment_by_id(conn, assignment_id)

    set_clauses = [sql.SQL("{} = %s").format(sql.Identifier(col)) for col in update_data.keys()]
    set_clauses.append(sql.SQL("updated_at = now()"))
    query = sql.SQL("UPDATE assignments SET {} WHERE id = %s RETURNING *;").format(sql.SQL(", ").join(set_clauses))
    values = list(update_data.values()) + [assignment_id]

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, values)
        return await cur.fetchone()


async def delete_assignment(conn: psycopg.AsyncConnection, assignment_id: UUID) -> bool:
    """Удалить задание."""
    query = "DELETE FROM assignments WHERE id = %s;"
    async with conn.cursor() as cur:
        await cur.execute(query, (assignment_id,))
        return cur.rowcount > 0


# ==============================================================================
# 8. ПЕРСОНАЛЬНЫЕ НАЗНАЧЕНИЯ ЗАДАНИЙ (Таблица assignment_targets)
# ==============================================================================

async def add_assignment_target(conn: psycopg.AsyncConnection, data: AssignmentTargetCreateRequest) -> dict:
    """Назначить задание персонально студенту."""
    query = """
        INSERT INTO assignment_targets (assignment_id, member_id)
        VALUES (%s, %s)
        RETURNING *;
    """
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (data.assignment_id, data.member_id))
        return await cur.fetchone()


async def get_assignment_targets(conn: psycopg.AsyncConnection, assignment_id: UUID) -> list[dict]:
    """Список персонально назначенных студентов."""
    query = """
        SELECT at.id, at.assignment_id, at.member_id, at.assigned_at,
               dm.user_id, u.first_name, u.last_name, u.email
        FROM assignment_targets at
        JOIN discipline_members dm ON at.member_id = dm.id
        JOIN users u ON dm.user_id = u.id
        WHERE at.assignment_id = %s;
    """
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (assignment_id,))
        return await cur.fetchall()


async def remove_assignment_target(conn: psycopg.AsyncConnection, target_id: UUID) -> bool:
    """Отозвать персональное назначение."""
    query = "DELETE FROM assignment_targets WHERE id = %s;"
    async with conn.cursor() as cur:
        await cur.execute(query, (target_id,))
        return cur.rowcount > 0


# ==============================================================================
# 9. СДАЧИ ЗАДАНИЙ И ОЦЕНИВАНИЕ (Таблица submissions)
# ==============================================================================

async def create_submission(conn: psycopg.AsyncConnection, data: SubmissionCreateRequest) -> dict:
    """Сдать работу (создать новую попытку сдачи)."""
    # Рассчитываем номер попытки attempt_number
    count_query = """
        SELECT COALESCE(MAX(attempt_number), 0) + 1 AS next_attempt
        FROM submissions
        WHERE assignment_id = %s AND submitted_by = %s;
    """
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(count_query, (data.assignment_id, data.submitted_by))
        next_attempt = (await cur.fetchone())["next_attempt"]

        insert_query = """
            INSERT INTO submissions (assignment_id, team_id, submitted_by, status, attempt_number, answer_text)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *;
        """
        values = (data.assignment_id, data.team_id, data.submitted_by, data.status, next_attempt, data.answer_text)
        await cur.execute(insert_query, values)
        return await cur.fetchone()


async def get_submission_by_id(conn: psycopg.AsyncConnection, submission_id: UUID) -> dict | None:
    """Получить сдачу по ID."""
    query = "SELECT * FROM submissions WHERE id = %s;"
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (submission_id,))
        return await cur.fetchone()


async def get_submissions_by_assignment(
    conn: psycopg.AsyncConnection, assignment_id: UUID, status: str | None = None
) -> list[dict]:
    """Список сданных работ по заданию (с фильтрацией: проверенные/непроверенные)."""
    query = """
        SELECT s.*, u.first_name, u.last_name, u.email, t.name AS team_name
        FROM submissions s
        JOIN users u ON s.submitted_by = u.id
        LEFT JOIN teams t ON s.team_id = t.id
        WHERE s.assignment_id = %s
    """
    params: list[Any] = [assignment_id]
    if status:
        query += " AND s.status = %s"
        params.append(status)
    query += " ORDER BY s.submitted_at DESC;"

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, params)
        return await cur.fetchall()


async def get_user_submissions(
    conn: psycopg.AsyncConnection, user_id: UUID, assignment_id: UUID
) -> list[dict]:
    """История попыток сдачи конкретного студента по заданию."""
    query = """
        SELECT * FROM submissions
        WHERE submitted_by = %s AND assignment_id = %s
        ORDER BY attempt_number DESC;
    """
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (user_id, assignment_id))
        return await cur.fetchall()


async def get_student_discipline_grades(
    conn: psycopg.AsyncConnection, discipline_id: UUID, user_id: UUID
) -> list[dict]:
    """Журнал баллов студента по всем заданиям курса."""
    query = """
        SELECT a.id AS assignment_id, a.title AS assignment_title, a.max_score, a.due_date,
               s.id AS submission_id, s.status, s.score, s.feedback, s.graded_at, s.attempt_number
        FROM assignments a
        JOIN lessons l ON a.lesson_id = l.id
        LEFT JOIN submissions s ON s.assignment_id = a.id AND s.submitted_by = %s
        WHERE l.discipline_id = %s AND a.is_published = TRUE
        ORDER BY l.order_index, a.created_at;
    """
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (user_id, discipline_id))
        return await cur.fetchall()


async def update_submission(
    conn: psycopg.AsyncConnection, submission_id: UUID, data: SubmissionUpdateRequest
) -> dict | None:
    """Обновление черновика сдачи работы."""
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return await get_submission_by_id(conn, submission_id)

    set_clauses = [sql.SQL("{} = %s").format(sql.Identifier(col)) for col in update_data.keys()]
    set_clauses.append(sql.SQL("updated_at = now()"))
    query = sql.SQL("UPDATE submissions SET {} WHERE id = %s RETURNING *;").format(sql.SQL(", ").join(set_clauses))
    values = list(update_data.values()) + [submission_id]

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, values)
        return await cur.fetchone()


async def review_submission(
    conn: psycopg.AsyncConnection, submission_id: UUID, data: SubmissionReviewRequest
) -> dict | None:
    """Проверка работы преподавателем: выставление оценки ('graded') или возврат на доработку ('returned')."""
    query = """
        UPDATE submissions
        SET status = %s, score = %s, feedback = %s, grader_id = %s, graded_at = now()
        WHERE id = %s
        RETURNING *;
    """
    values = (data.status, data.score, data.feedback, data.grader_id, submission_id)
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, values)
        return await cur.fetchone()


# ==============================================================================
# 10. ФАЙЛЫ И РЕСУРСЫ (Таблица files)
# ==============================================================================

async def create_file(conn: psycopg.AsyncConnection, data: FileCreateRequest) -> dict:
    """Зарегистрировать файл или ссылку."""
    meta_json = json.dumps(data.meta) if data.meta else None
    query = """
        INSERT INTO files (uploader_id, lesson_id, submission_id, file_type, url, file_name, size_bytes, mime_type, meta)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *;
    """
    values = (
        data.uploader_id, data.lesson_id, data.submission_id, data.file_type,
        data.url, data.file_name, data.size_bytes, data.mime_type, meta_json
    )
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, values)
        return await cur.fetchone()


async def get_file_by_id(conn: psycopg.AsyncConnection, file_id: UUID) -> dict | None:
    """Получить файл по ID."""
    query = "SELECT * FROM files WHERE id = %s;"
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (file_id,))
        return await cur.fetchone()


async def get_files_by_lesson(conn: psycopg.AsyncConnection, lesson_id: UUID) -> list[dict]:
    """Список материалов и ссылок к уроку."""
    query = "SELECT * FROM files WHERE lesson_id = %s ORDER BY created_at ASC;"
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (lesson_id,))
        return await cur.fetchall()


async def get_files_by_submission(conn: psycopg.AsyncConnection, submission_id: UUID) -> list[dict]:
    """Список файлов, прикрепленных студентом к сдаче задания."""
    query = "SELECT * FROM files WHERE submission_id = %s ORDER BY created_at ASC;"
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (submission_id,))
        return await cur.fetchall()


async def delete_file(conn: psycopg.AsyncConnection, file_id: UUID) -> bool:
    """Удалить файл."""
    query = "DELETE FROM files WHERE id = %s;"
    async with conn.cursor() as cur:
        await cur.execute(query, (file_id,))
        return cur.rowcount > 0
