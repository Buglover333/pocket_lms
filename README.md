# Pocket LMS API

Реализованы авторизация, профиль, курсы, модули, материалы, задания, сдачи, оценки, команды и файлы. Полный перечень маршрутов — docs/ENDPOINTS.txt, типы и примеры — API_CONTRACT_REVIEW.md и openapi.json.

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
Далее примените схему и миграции и запустите API:

```sh
uv run --env-file .env python scripts/migrate.py
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
TEST_DATABASE_URL='postgresql://myuser:mypassword@127.0.0.1:5433/pocket_lms_api_test_local' PYTHONPATH=src uv run python -m unittest discover -s tests -p 'test_api*.py' -v
```

Создание тестовой базы и схемы требуется один раз. Затем повторяйте только последнюю
команду. Тесты создают и убирают свои записи. Они проверяют контракт API с настоящим
PostgreSQL, включая фильтрацию членства, дедупликацию модулей, ошибки доступа,
валидацию и конкурентную регистрацию. Комплексная проверка CRUD-методов коллеги запускается отдельно на той же тестовой базе:

```sh
TEST_DATABASE_URL='postgresql://myuser:mypassword@127.0.0.1:5433/pocket_lms_api_test_local' uv run python tests/test_crud.py
```

tests/test_crud.py учитывает TEST_DATABASE_URL; без этой переменной сохраняется
его исходный адрес подключения из проекта.


## Организация кода

Включены изменения CRUD-слоя из коммита 352b8b6 ветки feature/db-schema-and-crud.

- src/backend/api/main.py — только сборка приложения и подключение роутеров.
- src/backend/api/routers/ — HTTP-обработчики всех перечисленных разделов.
- src/backend/api/access.py — общие проверки доступа к объектам.
- src/backend/services/storage.py — приватное S3-хранилище.
- src/backend/api/dependencies.py — получение подключения и проверка текущего пользователя.
- src/backend/api/security.py — хеширование паролей и JWT.
- src/backend/db/connection.py — подключение к PostgreSQL и границы транзакции.
- src/backend/db/methods.py — SQL и CRUD-методы всех сущностей проекта.
- src/backend/schemas/data.py — общие модели данных и схемы CRUD.
- src/backend/schemas/api.py — публичные ответы API на основе общих моделей.

Роутеры и HTTP-зависимости вызывают db.methods; SQL и создание соединений
находятся в слое db. Внутренний метод get_user_disciplines по умолчанию возвращает
все членства, как до объединения. Для публичного списка курсов роутер передаёт
active_only=True. Из внутренних результатов в публичный ответ попадают только
поля, перечисленные в модели ответа.

HTTP-контракт API_DESCRIPTION.md сохранён, включая POST /app, старые адреса
/get_* и параметр user_id. Переименование адресов и получение user_id только
из токена требуют отдельного согласования контракта командой.


## Локальная проверка 25.10.2026

Исправления подготовлены для ветки endpoints; публикация на GitHub выполняется отдельно. См. docs/REVIEW_2026-10-25.md, API_CONTRACT_REVIEW.md и TEST_RESULTS_REVIEW.md. Публичное обновление профиля ограничено именем и фамилией. Список сдач ограничен выбранным студентом. Для файлов S3 используется create_file_upload → отправка формы в хранилище → complete_file_upload → get_file_download. Для S3 нужны bucket, IAM credentials/роль и CORS провайдера; настоящие ключи не входят в проект.


## Аутентификация и права (feature/authentication)

Подробное описание для ревью и защиты: [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md).
Email + пароль, без Яндекса, подтверждения email и внешней почты. Роль преподавателя
действует в конкретном курсе; создатель модуля управляет всем своим модулем.

Перед первым запуском и после обновления кода выполните:

```sh
uv run --env-file .env python scripts/migrate.py
```

Для локального Swagger по HTTP задайте в `.env` `AUTH_COOKIE_SECURE=false`.
Для развёртывания по HTTPS оставьте `true` (значение по умолчанию).
После миграции прежние JWT без сессии больше не принимаются — войдите заново.
В тестовой команде выше также добавьте `AUTH_COOKIE_SECURE=false` перед `PYTHONPATH`.
Новый `/create_invitation` принимает JSON с ролью и курсом/выбранными курсами модуля.
Старые статические коды из карточки курса не дают права присоединиться: создайте приглашение.
