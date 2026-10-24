# API Pocket LMS

Базовый формат обмена данными — JSON. Все идентификаторы имеют тип UUID.

## Эндпоинты

| Метод | URL | Назначение | Авторизация |
|---|---|---|---|
| `POST` | `/app` | Отдать frontend приложения | Нет |
| `POST` | `/auth` | Вход пользователя | Нет |
| `POST` | `/register` | Регистрация пользователя | Нет |
| `GET` | `/get_courses?user_id={uuid}` | Курсы пользователя | Bearer token |
| `GET` | `/get_modules?user_id={uuid}` | Модули пользователя | Bearer token |
| `GET` | `/get_user_info?user_id={uuid}` | Профиль пользователя | Bearer token |

Для защищённых запросов:

```http
Authorization: Bearer <access_token>
```

`user_id` в запросе должен совпадать с пользователем, указанным в токене.

---

## `POST /app`

Возвращает собранный frontend приложения.

### Запрос

Тело запроса отсутствует.

```http
POST /app
```

### Ответ

```http
200 OK
Content-Type: text/html
```

База данных не используется.

---

## `POST /auth`

Авторизует пользователя по email и паролю.

### Запрос

```json
{
  "email": "student@example.com",
  "password": "Password123"
}
```

### Ответ `200 OK`

```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "user_id": "2a87c945-1a64-4ba0-b771-18c9ea101256"
}
```

### Работа с БД

Пользователь ищется в таблице `users` по условиям:

```text
users.email = email
users.is_active = true
```

Переданный пароль сравнивается с `users.password_hash`. Сам пароль в БД не хранится.

### Ошибки

| Код | Причина |
|---|---|
| `401` | Неверный email или пароль |
| `422` | Неверный формат запроса |

---

## `POST /register`

Создаёт нового пользователя.

### Запрос

```json
{
  "email": "student@example.com",
  "first_name": "Иван",
  "last_name": "Иванов",
  "password": "Password123",
  "password_confirm": "Password123"
}
```

### Валидация

- `email` должен иметь корректный формат и быть уникальным;
- `first_name` и `last_name` обязательны;
- длина пароля — от 8 до 64 символов;
- пароль должен содержать цифру и заглавную букву;
- `password` и `password_confirm` должны совпадать.

### Ответ `201 Created`

```json
{
  "id": "2a87c945-1a64-4ba0-b771-18c9ea101256",
  "email": "student@example.com",
  "first_name": "Иван",
  "last_name": "Иванов",
  "is_active": true,
  "created_at": "2026-10-23T12:00:00Z"
}
```

### Работа с БД

Создаётся запись в таблице `users`:

| Запрос | БД |
|---|---|
| `email` | `users.email` |
| `first_name` | `users.first_name` |
| `last_name` | `users.last_name` |
| хеш `password` | `users.password_hash` |

`password_confirm` используется только для проверки и в БД не записывается.

### Ошибки

| Код | Причина |
|---|---|
| `409` | Пользователь с таким email уже существует |
| `422` | Данные не прошли валидацию |

---

## `GET /get_courses`

Возвращает курсы, в которых пользователь является активным участником.

### Запрос

```http
GET /get_courses?user_id=2a87c945-1a64-4ba0-b771-18c9ea101256
Authorization: Bearer <access_token>
```

### Ответ `200 OK`

```json
{
  "items": [
    {
      "id": "713f5172-a8b8-429d-8104-c53bb116ac21",
      "module_id": "d701cddd-9014-458d-9135-59711e5fd522",
      "author_id": "a28fbab1-0d14-4012-bdc7-25183b657249",
      "title": "Программирование",
      "discipline_type": "module",
      "status": "published",
      "description": "Основы разработки программного обеспечения",
      "cover_file_id": null,
      "ends_at": "2026-12-25",
      "role": "student",
      "team_id": null
    }
  ]
}
```

Если курсов нет:

```json
{
  "items": []
}
```

### Работа с БД

Используются таблицы `discipline_members` и `disciplines`:

```text
discipline_members.user_id = user_id
discipline_members.status = "active"
discipline_members.discipline_id = disciplines.id
```

Данные курса берутся из `disciplines`. Поля `role` и `team_id` берутся из `discipline_members`.

Допустимые значения:

- `discipline_type`: `module`, `core`, `elective`;
- `status`: `draft`, `published`, `archived`;
- `role`: `owner`, `teacher`, `student`.

### Ошибки

| Код | Причина |
|---|---|
| `401` | Пользователь не авторизован |
| `403` | Запрошены курсы другого пользователя |
| `404` | Пользователь не найден |
| `422` | `user_id` не является UUID |

---

## `GET /get_modules`

Возвращает модули, к которым относятся курсы пользователя.

### Запрос

```http
GET /get_modules?user_id=2a87c945-1a64-4ba0-b771-18c9ea101256
Authorization: Bearer <access_token>
```

### Ответ `200 OK`

```json
{
  "items": [
    {
      "id": "d701cddd-9014-458d-9135-59711e5fd522",
      "title": "Разработка программных систем",
      "description": "Проектирование и разработка ПО",
      "curator_id": "a28fbab1-0d14-4012-bdc7-25183b657249"
    }
  ]
}
```

Если модулей нет:

```json
{
  "items": []
}
```

### Работа с БД

Используются таблицы `discipline_members`, `disciplines` и `modules`:

```text
discipline_members.user_id = user_id
discipline_members.status = "active"
discipline_members.discipline_id = disciplines.id
disciplines.module_id = modules.id
```

Если у курса `disciplines.module_id = null`, такой курс не добавляет модуль в ответ. Повторяющиеся модули удаляются из результата.

### Ошибки

| Код | Причина |
|---|---|
| `401` | Пользователь не авторизован |
| `403` | Запрошены модули другого пользователя |
| `404` | Пользователь не найден |
| `422` | `user_id` не является UUID |

---

## `GET /get_user_info`

Возвращает профиль пользователя.

### Запрос

```http
GET /get_user_info?user_id=2a87c945-1a64-4ba0-b771-18c9ea101256
Authorization: Bearer <access_token>
```

### Ответ `200 OK`

```json
{
  "id": "2a87c945-1a64-4ba0-b771-18c9ea101256",
  "email": "student@example.com",
  "first_name": "Иван",
  "last_name": "Иванов",
  "middle_name": null,
  "avatar_id": null,
  "is_admin": false,
  "is_active": true,
  "created_at": "2026-10-23T12:00:00Z",
  "updated_at": null
}
```

### Работа с БД

Данные берутся из таблицы `users`:

```text
users.id = user_id
users.is_active = true
```

В ответ не передаются `password_hash` и `yandex_id`.

### Ошибки

| Код | Причина |
|---|---|
| `401` | Пользователь не авторизован |
| `403` | Запрошен профиль другого пользователя |
| `404` | Пользователь не найден |
| `422` | `user_id` не является UUID |

---

## Общий формат ошибки

```json
{
  "detail": "Описание ошибки"
}
```

Связи таблиц, на которых основаны методы получения данных:

```text
users.id
  → discipline_members.user_id
  → discipline_members.discipline_id
  → disciplines.id
  → disciplines.module_id
  → modules.id
```
