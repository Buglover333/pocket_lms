"""
Комплексное тестирование CRUD-методов для всех сущностей платформы:
- users, modules, disciplines
- teams, discipline_members
- lessons, assignments, assignment_targets
- submissions (сдача и проверка преподавателем)
- files (материалы и вложения)

Запуск:
    1. Убедиться, что Docker запущен: docker compose up -d
    2. Выполнить: uv run python tests/test_crud.py
"""

import asyncio
from datetime import datetime, timezone
import sys
from pathlib import Path
from uuid import uuid4

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Добавляем путь к src для корректных импортов
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import psycopg

from backend.schemas.data import (
    AssignmentCreateRequest,
    AssignmentTargetCreateRequest,
    DisciplineCreateRequest,
    DisciplineMemberCreateRequest,
    FileCreateRequest,
    LessonCreateRequest,
    ModuleCreateRequest,
    ModuleUpdateRequest,
    SubmissionCreateRequest,
    SubmissionReviewRequest,
    TeamCreateRequest,
    UserCreate,
)
from backend.db.methods import (
    add_assignment_target,
    add_discipline_member,
    create_assignment,
    create_discipline,
    create_file,
    create_lesson,
    create_module,
    create_submission,
    create_team,
    create_user,
    delete_assignment,
    delete_discipline,
    delete_file,
    delete_lesson,
    delete_module,
    delete_team,
    delete_user,
    get_assignment_by_id,
    get_discipline_deadlines,
    get_discipline_members_with_profiles,
    get_files_by_lesson,
    get_lessons_by_discipline,
    get_module_by_id,
    get_student_discipline_grades,
    get_submissions_by_assignment,
    get_team_members,
    get_user_by_id,
    remove_discipline_member,
    review_submission,
    update_module,
)

CONN_INFO = "postgresql://myuser:mypassword@localhost:5433/mydb"


async def main():
    print("[1] Подключаемся к базе данных...")
    async with await psycopg.AsyncConnection.connect(CONN_INFO) as conn:
        print("[OK] Подключение успешно установлено!")

        # 1. ТЕСТ ПОЛЬЗОВАТЕЛЕЙ (Преподаватель и Студент)
        print("\n--- ТЕСТ 1: Пользователи (Users) ---")
        teacher_in = UserCreate(
            email=f"teacher_{uuid4().hex[:6]}@schoolx.ru",
            password_hash="hashed_secret_123",
            first_name="Иван",
            last_name="Преподавателев",
        )
        teacher = await create_user(conn, teacher_in)
        teacher_id = teacher["id"]
        print(f"[OK] Создан преподаватель: {teacher['first_name']} {teacher['last_name']} (ID: {teacher_id})")

        student_in = UserCreate(
            email=f"student_{uuid4().hex[:6]}@schoolx.ru",
            password_hash="hashed_secret_456",
            first_name="Петр",
            last_name="Студентов",
        )
        student = await create_user(conn, student_in)
        student_id = student["id"]
        print(f"[OK] Создан студент: {student['first_name']} {student['last_name']} (ID: {student_id})")

        try:
            # 2. ТЕСТ МОДУЛЕЙ
            print("\n--- ТЕСТ 2: Модули (Modules) ---")
            mod_data = ModuleCreateRequest(
                title="Веб-разработка 3 курс",
                description="FastAPI, React, PostgreSQL",
                curator_id=teacher_id,
            )
            module = await create_module(conn, mod_data)
            mod_id = module["id"]
            print(f"[OK] Модуль создан: {module['title']} (ID: {mod_id})")

            updated_mod = await update_module(conn, mod_id, ModuleUpdateRequest(title="Веб-разработка (Обновлен)"))
            assert updated_mod["title"] == "Веб-разработка (Обновлен)"
            print(f"[OK] Модуль обновлен: {updated_mod['title']}")

            # 3. ТЕСТ ДИСЦИПЛИН / КУРСОВ
            print("\n--- ТЕСТ 3: Дисциплины (Disciplines) ---")
            invite = f"INV-{uuid4().hex[:6].upper()}"
            disc_data = DisciplineCreateRequest(
                title="Бэкенд на FastAPI",
                module_id=mod_id,
                author_id=teacher_id,
                invite_code=invite,
                description="Изучаем асинхронные методы и Pydantic",
            )
            disc = await create_discipline(conn, disc_data)
            disc_id = disc["id"]
            print(f"[OK] Дисциплина создана: {disc['title']} (Инвайт-код: {disc['invite_code']})")

            # 4. ТЕСТ КОМАНД (Teams)
            print("\n--- ТЕСТ 4: Команды (Teams) ---")
            team_data = TeamCreateRequest(
                discipline_id=disc_id,
                name="Команда Альфа",
                description="Проект системы управления знаниями",
            )
            team = await create_team(conn, team_data)
            team_id = team["id"]
            print(f"[OK] Команда создана: {team['name']} (ID: {team_id})")

            # 5. ТЕСТ УЧАСТНИКОВ КУРСА (Discipline Members & Contacts)
            print("\n--- ТЕСТ 5: Участники курса и раздел Контакты ---")
            member_data = DisciplineMemberCreateRequest(
                discipline_id=disc_id,
                user_id=student_id,
                role="student",
                status="active",
                team_id=team_id,
            )
            member = await add_discipline_member(conn, member_data)
            member_id = member["id"]
            print(f"[OK] Студент записан на курс и распределен в команду (Member ID: {member_id})")

            # Проверяем получение участников команды
            team_members = await get_team_members(conn, team_id)
            assert len(team_members) >= 1
            print(f"[OK] Участники команды проверены: {team_members[0]['first_name']} {team_members[0]['last_name']}")

            # Проверяем раздел Контакты (с именами из users)
            contacts = await get_discipline_members_with_profiles(conn, disc_id)
            assert len(contacts) >= 1
            print(f"[OK] Вкладка Контакты курса: получен участник {contacts[0]['email']}")

            # 6. ТЕСТ УРОКОВ (Lessons)
            print("\n--- ТЕСТ 6: Уроки (Lessons) ---")
            lesson_data = LessonCreateRequest(
                discipline_id=disc_id,
                title="Урок 1: Архитектура REST API",
                order_index=1,
                content_markdown="# Введение в FastAPI",
                is_published=True,
            )
            lesson = await create_lesson(conn, lesson_data)
            lesson_id = lesson["id"]
            print(f"[OK] Урок создан: {lesson['title']} (ID: {lesson_id})")

            lessons = await get_lessons_by_discipline(conn, disc_id)
            assert len(lessons) >= 1
            print(f"[OK] Список уроков получен: {len(lessons)} шт.")

            # 7. ТЕСТ ФАЙЛОВ И МАТЕРИАЛОВ (Files / Library)
            print("\n--- ТЕСТ 7: Файлы и библиотека материалов (Files) ---")
            file_data = FileCreateRequest(
                uploader_id=teacher_id,
                lesson_id=lesson_id,
                file_type="document",
                url="https://disk.yandex.ru/d/example_methodics",
                file_name="Методичка_по_FastAPI.pdf",
                size_bytes=1024500,
                mime_type="application/pdf",
            )
            attached_file = await create_file(conn, file_data)
            file_id = attached_file["id"]
            print(f"[OK] Файл прикреплен к уроку: {attached_file['file_name']} (ID: {file_id})")

            lesson_files = await get_files_by_lesson(conn, lesson_id)
            assert len(lesson_files) >= 1
            print(f"[OK] Материалы к уроку получены из БД: {lesson_files[0]['url']}")

            # 8. ТЕСТ ЗАДАНИЙ И КАЛЕНДАРЯ (Assignments & Deadlines)
            print("\n--- ТЕСТ 8: Задания и Календарь дедлайнов (Assignments) ---")
            due = datetime.now(timezone.utc)
            assign_data = AssignmentCreateRequest(
                lesson_id=lesson_id,
                title="Лабораторная работа 1: Создание API",
                description_markdown="Реализовать эндпоинты по ТЗ",
                target_type="all",
                is_team_work=True,
                max_score=100,
                due_date=due,
            )
            assignment = await create_assignment(conn, assign_data)
            assign_id = assignment["id"]
            print(f"[OK] Задание создано: {assignment['title']} (ID: {assign_id})")

            # Проверяем дедлайны для вкладки Календарь
            deadlines = await get_discipline_deadlines(conn, disc_id)
            assert len(deadlines) >= 1
            print(f"[OK] Календарь дедлайнов курса: найдено задание с дедлайном {deadlines[0]['title']}")

            # Персональная выдача (Assignment Target)
            target = await add_assignment_target(
                conn, AssignmentTargetCreateRequest(assignment_id=assign_id, member_id=member_id)
            )
            target_id = target["id"]
            print(f"[OK] Персональное назначение создано (Target ID: {target_id})")

            # 9. ТЕСТ СДАЧИ РАБОТ И ОЦЕНИВАНИЯ (Submissions & Review)
            print("\n--- ТЕСТ 9: Сдача работы, проверка преподавателем и Журнал баллов ---")
            sub_data = SubmissionCreateRequest(
                assignment_id=assign_id,
                team_id=team_id,
                submitted_by=student_id,
                answer_text="Ссылка на pull request: https://github.com/example/pr/1",
                status="submitted",
            )
            submission = await create_submission(conn, sub_data)
            sub_id = submission["id"]
            print(f"[OK] Студент сдал работу: попытка #{submission['attempt_number']}, статус: {submission['status']}")

            # Преподаватель смотрит непроверенные работы
            unreviewed = await get_submissions_by_assignment(conn, assign_id, status="submitted")
            assert len(unreviewed) >= 1
            print(f"[OK] Ведомость преподавателя: найдено непроверенных работ: {len(unreviewed)}")

            # Преподаватель оценивает работу и пишет рецензию
            review_data = SubmissionReviewRequest(
                status="graded",
                score=95.0,
                feedback="Отличная реализация, чистая архитектура и типизация!",
                grader_id=teacher_id,
            )
            graded_sub = await review_submission(conn, sub_id, review_data)
            assert graded_sub["status"] == "graded"
            assert float(graded_sub["score"]) == 95.0
            print(f"[OK] Работа проверена преподавателем: оценка {graded_sub['score']}, статус: {graded_sub['status']}")

            # Студент смотрит журнал баллов
            grades = await get_student_discipline_grades(conn, disc_id, student_id)
            assert len(grades) >= 1
            print(f"[OK] Журнал баллов студента: задание '{grades[0]['assignment_title']}', балл: {grades[0]['score']}")

            # 10. ОЧИСТКА ТЕСТОВЫХ ДАННЫХ
            print("\n--- Очистка тестовых данных ---")
            await delete_file(conn, file_id)
            await delete_assignment(conn, assign_id)
            await delete_lesson(conn, lesson_id)
            await remove_discipline_member(conn, member_id)
            await delete_team(conn, team_id)
            await delete_discipline(conn, disc_id)
            await delete_module(conn, mod_id)
            await delete_user(conn, student_id)
            await delete_user(conn, teacher_id)
            await conn.commit()
            print("[OK] Все тестовые записи каскадно очищены, база в чистоте!")

            print("\n🎉 ВСЕ ТЕСТЫ ДЛЯ ВСЕХ 10 СУЩНОСТЕЙ ЮЗЕР-ФЛОУ УСПЕШНО ПРОЙДЕНЫ! 🎉")

        except Exception as e:
            await conn.rollback()
            print(f"\n[ERROR] Ошибка в тесте: {e}")
            raise e


if __name__ == "__main__":
    asyncio.run(main())
