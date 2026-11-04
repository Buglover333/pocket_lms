# API Pocket LMS — 04.11.2026

Текущий контракт: feature/api-contract-review. Точные схемы и примеры — [API_CONTRACT_REVIEW.md](API_CONTRACT_REVIEW.md), OpenAPI — [openapi.json](openapi.json). Решения аналитиков — [docs/API_REVIEW_2026-11-04.md](docs/API_REVIEW_2026-11-04.md).

GET /get_courses, /get_modules, /get_assignments, /get_groups, /get_members, /get_team_members и /get_grades возвращают массивы. Материалы и сдачи сохраняют MaterialsResponse/SubmissionsResponse с items.

Публичное обновление профиля: first_name, last_name, middle_name, avatar_id. Email/SMTP отложены. Самостоятельное удаление — DELETE /delete_account с current_password. При регистрации действует список российских почтовых сервисов.

GET /get_course_data возвращает карточку без материалов и инвайт-кода. GET /get_module_data возвращает поля ModuleResponse и disciplines без инвайт-кодов. Создание курса требует draft/published, код генерирует сервер. Приглашения создаются отдельно с ролью и областью.

GET /app отдаёт frontend/dist/index.html как text/html. Пока сборки нет — 503. Для размещения frontend и API на одном origin CORS между ними не требуется. Это опциональная раздача сборки; frontend ещё не реализован.

| Метод | Путь | Назначение | Успешный ответ |
|---|---|---|---|
| POST | `/register` | Register | 201 UserPublicBase |
| POST | `/auth` | Authenticate | 200 AuthResponse |
| POST | `/auth/refresh` | Обновить вход на текущем устройстве | 200 AuthResponse |
| POST | `/auth/logout` | Выйти на текущем устройстве | 200 SuccessResponse |
| GET | `/auth/sessions` | Посмотреть свои активные устройства | 200 SessionList |
| POST | `/auth/change_password` | Сменить пароль | 200 MessageResponse |
| POST | `/admin/password_reset` | Выдать одноразовый код восстановления | 200 ResetCodeResponse |
| POST | `/auth/reset_password` | Восстановить пароль по коду администратора | 200 MessageResponse |
| PATCH | `/admin/account_status` | Заблокировать или разблокировать аккаунт | 200 AccountStatusResponse |
| GET | `/get_user_info` | Get User Info | 200 UserProfileResponse |
| PATCH | `/update_settings` | Update Settings | 200 UserProfileResponse |
| DELETE | `/delete_account` | Деактивировать свой аккаунт | 200 SuccessResponse |
| GET | `/get_courses` | Get Courses | 200 array<CourseItem> |
| GET | `/get_course_data` | Get Course Data | 200 DisciplineResponse |
| POST | `/create_course` | Create Course | 201 CourseCreatedResponse |
| PATCH | `/update_course` | Update Course | 200 DisciplineResponse |
| POST | `/create_invitation` | Create Invitation | 201 InvitationResponse |
| POST | `/accept_invitation` | Accept Invitation | 200 InvitationAcceptance |
| DELETE | `/revoke_invitation` | Revoke Invitation | 200 SuccessResponse |
| DELETE | `/remove_course_member` | Remove Course Member | 200 SuccessResponse |
| GET | `/get_members` | Get Members | 200 array<CourseMemberResponse> |
| GET | `/get_modules` | Get Modules | 200 array<ModuleResponse> |
| GET | `/get_module_data` | Get Module Data | 200 ModuleDataResponse |
| POST | `/create_module` | Create Module | 201 ModuleResponse |
| PATCH | `/update_module` | Update Module | 200 ModuleResponse |
| DELETE | `/remove_module_member` | Remove Module Member | 200 SuccessResponse |
| GET | `/get_materials` | Get Materials | 200 MaterialsResponse |
| GET | `/get_material_data` | Get Material Data | 200 MaterialDataResponse |
| POST | `/create_material` | Create Material | 201 LessonResponse |
| PATCH | `/update_material` | Update Material | 200 LessonResponse |
| DELETE | `/delete_material` | Delete Material | 200 SuccessResponse |
| GET | `/get_assignments` | Get Assignments | 200 array<AssignmentResponse> |
| GET | `/get_assignment_data` | Get Assignment Data | 200 AssignmentDataResponse |
| POST | `/create_assignment` | Create Assignment | 201 AssignmentResponse |
| PATCH | `/update_assignment` | Update Assignment | 200 AssignmentResponse |
| DELETE | `/delete_assignment` | Delete Assignment | 200 SuccessResponse |
| GET | `/get_calendar` | Get Calendar | 200 object |
| POST | `/submit_work` | Submit Work | 201 SubmissionResponse |
| POST | `/resubmit_work` | Resubmit Work | 200 SubmissionResponse |
| GET | `/get_submissions` | Get Submissions | 200 SubmissionsResponse |
| GET | `/get_submission_data` | Get Submission Data | 200 SubmissionDataResponse |
| POST | `/grade_submission` | Grade Submission | 200 SubmissionResponse |
| POST | `/return_submission` | Return Submission | 200 SubmissionResponse |
| GET | `/get_grades` | Get Grades | 200 array<GradeResponse> |
| GET | `/get_groups` | Get Groups | 200 array<TeamResponse> |
| POST | `/create_group` | Create Group | 201 TeamResponse |
| GET | `/get_team_members` | Get Team Members | 200 array<CourseMemberResponse> |
| PATCH | `/update_group` | Update Group | 200 TeamResponse |
| DELETE | `/delete_group` | Delete Group | 200 SuccessResponse |
| POST | `/upload_file` | Upload File | 201 FileResponse |
| GET | `/get_file` | Get File | 200 FileResponse |
| DELETE | `/delete_file` | Delete File | 200 SuccessResponse |
| POST | `/create_file_upload` | Create File Upload | 201 FileUploadResponse |
| POST | `/complete_file_upload` | Complete File Upload | 200 FileResponse |
| GET | `/get_file_download` | Get File Download | 200 FileDownloadResponse |
| GET | `/app` | Frontend | 200 text/html |
