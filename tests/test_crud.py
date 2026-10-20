"""
Тестирование CRUD-методов для таблиц modules и disciplines.
"""

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Добавляем путь к src для импортов
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import psycopg

from backend.schemas.data import (
    ModuleCreateRequest,
    ModuleUpdateRequest,
    DisciplineCreateRequest,
    DisciplineUpdateRequest,
)
from backend.db.methods import (
    create_module,
    get_module_by_id,
    get_modules_list,
    update_module,
    delete_module,
    create_discipline,
    get_discipline_by_id,
    get_discipline_by_invite_code,
    get_disciplines_by_module,
    get_disciplines_list,
    update_discipline,
    delete_discipline,
)

CONN_INFO = "postgresql://myuser:mypassword@localhost:5433/mydb"


async def main():
    print("[1] Подключаемся к базе данных...")
    async with await psycopg.AsyncConnection.connect(CONN_INFO) as conn:
        print("[OK] Подключение успешно установлено!")

        # Создаем временного пользователя-преподавателя для тестов
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO users (email, first_name, last_name)
                VALUES ('test_teacher@schoolx.ru', 'Тест', 'Преподаватель')
                RETURNING id;
            """)
            teacher_id = (await cur.fetchone())[0]
            print(f"[OK] Создан тестовый преподаватель ID: {teacher_id}")

        try:
            # === ТЕСТЫ МОДУЛЕЙ ===

            print("\n--- ТЕСТ 1: Создание модуля ---")
            mod_data = ModuleCreateRequest(
                title="Веб-разработка 3 курс",
                description="Изучение FastAPI и PostgreSQL",
                curator_id=teacher_id,
            )
            module = await create_module(conn, mod_data)
            mod_id = module["id"]
            assert module["title"] == "Веб-разработка 3 курс"
            print(f"[OK] Модуль создан: {module['title']} (ID: {mod_id})")

            print("\n--- ТЕСТ 2: Получение модуля по ID ---")
            fetched_mod = await get_module_by_id(conn, mod_id)
            assert fetched_mod is not None
            assert fetched_mod["id"] == mod_id
            print(f"[OK] Модуль найден по ID: {fetched_mod['title']}")

            print("\n--- ТЕСТ 3: Список модулей ---")
            modules = await get_modules_list(conn)
            assert len(modules) >= 1
            print(f"[OK] Получен список модулей: {len(modules)} шт.")

            print("\n--- ТЕСТ 4: Обновление модуля ---")
            mod_update = ModuleUpdateRequest(title="Веб-разработка (Обновленный)")
            updated_mod = await update_module(conn, mod_id, mod_update)
            assert updated_mod["title"] == "Веб-разработка (Обновленный)"
            assert updated_mod["updated_at"] is not None
            print(f"[OK] Модуль обновлен: {updated_mod['title']}")

            # === ТЕСТЫ ДИСЦИПЛИН ===

            print("\n--- ТЕСТ 5: Создание дисциплины ---")
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
            assert disc["title"] == "Бэкенд на FastAPI"
            assert disc["status"] == "draft"
            print(f"[OK] Дисциплина создана: {disc['title']} (Инвайт-код: {disc['invite_code']})")

            print("\n--- ТЕСТ 6: Получение дисциплины по ID ---")
            fetched_disc = await get_discipline_by_id(conn, disc_id)
            assert fetched_disc is not None
            assert fetched_disc["id"] == disc_id
            print(f"[OK] Дисциплина найдена по ID: {fetched_disc['title']}")

            print("\n--- ТЕСТ 7: Поиск дисциплины по инвайт-коду ---")
            found = await get_discipline_by_invite_code(conn, invite)
            assert found is not None
            assert found["invite_code"] == invite
            print(f"[OK] Дисциплина найдена по инвайт-коду: {found['title']}")

            print("\n--- ТЕСТ 8: Список дисциплин по модулю ---")
            by_module = await get_disciplines_by_module(conn, mod_id)
            assert len(by_module) >= 1
            print(f"[OK] Дисциплины модуля: {len(by_module)} шт.")

            print("\n--- ТЕСТ 9: Список всех дисциплин ---")
            all_discs = await get_disciplines_list(conn)
            assert len(all_discs) >= 1
            print(f"[OK] Все дисциплины: {len(all_discs)} шт.")

            print("\n--- ТЕСТ 10: Обновление дисциплины ---")
            disc_update = DisciplineUpdateRequest(status="published")
            updated_disc = await update_discipline(conn, disc_id, disc_update)
            assert updated_disc["status"] == "published"
            assert updated_disc["updated_at"] is not None
            print(f"[OK] Статус обновлен на: {updated_disc['status']}")

            print("\n--- ТЕСТ 11: Удаление дисциплины ---")
            deleted_disc = await delete_discipline(conn, disc_id)
            assert deleted_disc is True
            check_disc = await get_discipline_by_id(conn, disc_id)
            assert check_disc is None
            print("[OK] Дисциплина удалена и не находится по ID")

            print("\n--- ТЕСТ 12: Удаление модуля ---")
            deleted_mod = await delete_module(conn, mod_id)
            assert deleted_mod is True
            check_mod = await get_module_by_id(conn, mod_id)
            assert check_mod is None
            print("[OK] Модуль удален и не находится по ID")

            # Очистка тестового пользователя
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM users WHERE id = %s;", (teacher_id,))

            await conn.commit()
            print("\n*** ВСЕ 12 ТЕСТОВ ПРОЙДЕНЫ УСПЕШНО! ***")

        except Exception as e:
            await conn.rollback()
            print(f"\n[ERROR] Тест провален: {e}")
            raise e


if __name__ == "__main__":
    asyncio.run(main())
