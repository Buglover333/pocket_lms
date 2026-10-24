# API Pocket LMS

Базовый формат обмена данными — JSON. Все идентификаторы имеют тип UUID.

## Сводная таблица всех эндпоинтов по роутерам

| Роутер | Метод | URL | Назначение | Таблицы БД | Авторизация |
|---|---|---|---|---|---|
| **auth / users** | `POST` | `/register` | Регистрация нового пользователя | `users` | Нет |
| **auth / users** | `POST` | `/auth` | Вход пользователя (получение токена) | `users` | Нет |
| **auth / users** | `GET` | `/get_user_info` | Профиль пользователя | `users` | Bearer |
| **auth / users** | `GET` | `/get_settings` | Настройки пользователя | `users` | Bearer |
| **auth / users** | `PATCH` | `/update_settings` | Обновление настроек/профиля | `users` | Bearer |
| **modules** | `GET` | `/get_modules` | Список модулей пользователя | `modules`, `disciplines`, `discipline_members` | Bearer |
| **modules** | `GET` | `/get_module_data` | Данные модуля и его дисциплины | `modules`, `disciplines` | Bearer |
| **modules** | `POST` | `/create_module` | Создание модуля | `modules` | Bearer |
| **modules** | `PATCH` | `/update_module` | Редактирование модуля | `modules` | Bearer |
| **courses** | `GET` | `/get_courses` | Курсы текущего пользователя | `disciplines`, `discipline_members` | Bearer |
| **courses** | `GET` | `/get_course_data` | Данные курса и список уроков | `disciplines`, `lessons` | Bearer |
| **courses** | `POST` | `/create_course` | Создание курса | `disciplines` | Bearer |
| **courses** | `PATCH` | `/update_course` | Редактирование курса | `disciplines` | Bearer |
| **courses** | `POST` | `/create_invitation` | Генерация/получение кода приглашения | `disciplines` | Bearer |
| **courses** | `POST` | `/accept_invitation` | Запись на курс по инвайт-коду | `disciplines`, `discipline_members` | Bearer |
| **courses** | `GET` | `/get_members` | Список участников курса | `discipline_members`, `users` | Bearer |
| **lessons** | `GET` | `/get_materials` | Материалы/уроки курса | `lessons` | Bearer |
| **lessons** | `GET` | `/get_material_data` | Содержимое урока и вложения | `lessons`, `files` | Bearer |
| **lessons** | `POST` | `/create_material` | Создание урока/материала | `lessons` | Bearer |
| **lessons** | `PATCH` | `/update_material` | Редактирование урока | `lessons` | Bearer |
| **lessons** | `DELETE` | `/delete_material` | Удаление урока | `lessons` | Bearer |
| **assignments** | `GET` | `/get_assignments` | Список заданий к уроку | `assignments` | Bearer |
| **assignments** | `GET` | `/get_assignment_data` | Детали задания, критерии, таргеты | `assignments`, `assignment_targets` | Bearer |
| **assignments** | `POST` | `/create_assignment` | Создание задания | `assignments`, `assignment_targets` | Bearer |
| **assignments** | `PATCH` | `/update_assignment` | Редактирование задания | `assignments` | Bearer |
| **assignments** | `DELETE` | `/delete_assignment` | Удаление задания | `assignments` | Bearer |
| **assignments** | `GET` | `/get_calendar` | Дедлайны по курсу | `assignments`, `lessons` | Bearer |
| **submissions** | `POST` | `/submit_work` | Сдача решения задания | `submissions` | Bearer |
| **submissions** | `POST` | `/resubmit_work` | Повторная сдача работы | `submissions` | Bearer |
| **submissions** | `GET` | `/get_submissions` | Список работ по заданию (преподаватель) | `submissions`, `users` | Bearer |
| **submissions** | `GET` | `/get_submission_data` | Детали сдачи и файлы | `submissions`, `files` | Bearer |
| **submissions** | `POST` | `/grade_submission` | Оценивание и фидбек | `submissions` | Bearer |
| **submissions** | `POST` | `/return_submission` | Возврат работы на доработку | `submissions` | Bearer |
| **submissions** | `GET` | `/get_grades` | Табель оценок студента | `submissions`, `assignments` | Bearer |
| **teams** | `GET` | `/get_groups` | Команды курса | `teams` | Bearer |
| **teams** | `POST` | `/create_group` | Создание команды | `teams` | Bearer |
| **teams** | `GET` | `/get_team_members` | Участники команды | `discipline_members`, `users` | Bearer |
| **teams** | `PATCH` | `/update_group` | Редактирование команды | `teams` | Bearer |
| **teams** | `DELETE` | `/delete_group` | Удаление команды | `teams` | Bearer |
| **files** | `POST` | `/upload_file` | Загрузка/регистрация файла | `files` | Bearer |
| **files** | `GET` | `/get_file` | Получение метаданных файла | `files` | Bearer |
| **files** | `DELETE` | `/delete_file` | Удаление файла | `files` | Bearer |
| **frontend** | `POST` | `/app` | Отдать frontend приложения | Нет | Нет |

---

## Авторизация

Для защищённых запросов используется стандартный Bearer Token:

```http
Authorization: Bearer <access_token>
```

---

## Архитектура и структура кода

Все эндпоинты разбиты по отдельным модулям в пакете `backend.api.routers`:
- `auth.py` — регистрация и вход в систему
- `users.py` — получение и обновление профиля и настроек
- `modules.py` — работа с образовательными модулями
- `courses.py` — управление курсами, участниками и инвайт-кодами
- `lessons.py` — материалы и уроки дисциплин
- `assignments.py` — создание и просмотр заданий, дедлайны
- `submissions.py` — приём работ, проверка преподавателем, выставление оценок
- `teams.py` — проектные команды обучающихся
- `files.py` — загрузка и доступ к учебным файлам
- `frontend.py` — отдача клиентского приложения

Обработчики HTTP-запросов вызывают исключительно готовые методы сервисного слоя из `backend.db.methods`.
Прямое обращение к базе данных или выполнение сырого SQL внутри роутеров запрещено и контролируется автоматическими архитектурными тестами (`tests/test_api_architecture.py`).
