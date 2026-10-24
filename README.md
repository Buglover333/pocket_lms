# Pocket LMS API

Контракт эндпоинтов находится в API_DESCRIPTION.md. Реализованы POST /app, POST /auth,
POST /register, GET /get_courses, GET /get_modules и GET /get_user_info.

## Локальный запуск

Требуются Python 3.12+, uv и запущенный Docker Desktop. Выполняйте команды из папки проекта.

```sh
uv sync
cp .env.example .env
docker compose up -d
```

В файле .env задайте JWT_SECRET. Для генерации значения:

```sh
uv run python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

DATABASE_URL в примере соответствует PostgreSQL из docker-compose.yml (порт 5433).
Далее запустите API:

```sh
uv run --env-file .env uvicorn --app-dir src backend.api.main:app --host 127.0.0.1 --port 8000
```

Swagger: http://127.0.0.1:8000/docs. Кнопка Authorize принимает только значение
access_token, без кавычек и без слова Bearer. user_id теперь возвращается при входе.
У нового пользователя списки курсов и модулей имеют вид {"items": []}.

## Уже существующая база

Для новой базы уникальный индекс email создаётся вместе со схемой.
Для существующей базы примените миграцию до запуска новой версии API:

```sh
docker compose exec -T postgres psql -U myuser -d mydb -v ON_ERROR_STOP=1 < src/backend/db/migrations/001_users_email_lower.sql
```

Индекс считает одинаковыми email, отличающиеся только регистром букв, и защищает
от двух одновременных регистраций. Если в старой базе уже есть такие дубликаты,
создание индекса остановится: сначала нужно разрешить конфликт записей.

## Будущий frontend

Frontend пока не разработан. POST /app возвращает 503 с объяснением, пока нет
frontend/dist/index.html. Другую папку сборки можно задать через FRONTEND_DIR
в .env. После появления сборки перезапустите API: POST /app отдаст index.html
с Content-Type: text/html. Если есть подпапка assets, она доступна по /assets.
Окончательные пути остальных ресурсов настраиваются под будущую сборку.
База данных для этого запроса не нужна.

## Проверка API с PostgreSQL

Проверки выполняются в отдельной базе. Не указывайте рабочую базу в TEST_DATABASE_URL.
Для локального Docker из этого проекта:

```sh
uv sync --group dev
docker compose exec -T postgres createdb -U myuser pocket_lms_api_test_local
docker compose exec -T postgres psql -U myuser -d pocket_lms_api_test_local -v ON_ERROR_STOP=1 < src/backend/db/schemas.sql
TEST_DATABASE_URL='postgresql://myuser:mypassword@127.0.0.1:5433/pocket_lms_api_test_local' PYTHONPATH=src uv run python -m unittest discover -s tests -p test_api.py -v
```

Создание тестовой базы и схемы требуется один раз. Затем повторяйте только последнюю
команду. Тесты создают и убирают свои записи. Они проверяют контракт API с настоящим
PostgreSQL, включая фильтрацию членства, дедупликацию модулей, ошибки доступа,
валидацию и конкурентную регистрацию. Старый tests/test_crud.py этой командой
не запускается.
