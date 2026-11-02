from datetime import date, datetime
import secrets
import re
from typing import Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)


# ==============================================================================
# 1. СХЕМЫ МОДУЛЕЙ (Таблица modules)
# ==============================================================================


class ModuleBase(BaseModel):
    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Название образовательного модуля",
    )
    description: str | None = Field(None, description="Описание программы модуля")

    @field_validator("title", mode="before")
    @classmethod
    def clean_title(cls, value):
        return value.strip() if isinstance(value, str) else value


class ModuleCreateRequest(ModuleBase):
    curator_id: UUID = Field(..., description="ID пользователя-куратора модуля")


class ModuleUpdateRequest(BaseModel):
    title: str | None = Field(
        None, max_length=255, description="Название образовательного модуля"
    )
    description: str | None = Field(None, description="Описание программы модуля")
    curator_id: UUID | None = Field(None, description="ID пользователя-куратора модуля")

    @field_validator("title", "curator_id", mode="before")
    @classmethod
    def required_value(cls, value):
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError("Поле не может быть пустым")
        return value.strip() if isinstance(value, str) else value


class ModuleResponse(ModuleBase):
    id: UUID
    curator_id: UUID
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 2. СХЕМЫ ДИСЦИПЛИН / КУРСОВ (Таблица disciplines)
# ==============================================================================

DisciplineType = Literal["module", "core", "elective"]
DisciplineStatus = Literal["draft", "published", "archived"]


class DisciplineBase(BaseModel):
    title: str = Field(
        ..., min_length=1, max_length=255, description="Название курса/предмета"
    )
    discipline_type: DisciplineType = Field(
        default="module", description="Тип: модуль программы, общевузовский, электив"
    )
    status: DisciplineStatus = Field(
        default="draft", description="Статус: черновик, опубликован, архив"
    )
    description: str | None = Field(None, description="Описание курса и требований")
    ends_at: date | None = Field(
        None, description="Дата окончания курса для авто-архивации"
    )

    @field_validator("title", mode="before")
    @classmethod
    def clean_title(cls, value):
        return value.strip() if isinstance(value, str) else value


class DisciplineCreateRequest(DisciplineBase):
    author_id: UUID = Field(
        ..., description="ID создателя курса (защита от курсов-сирот)"
    )
    invite_code: str = Field(
        default_factory=lambda: secrets.token_urlsafe(24),
        min_length=1,
        max_length=32,
        description="Совместимое поле курса; для записи создайте отдельное приглашение",
    )
    module_id: UUID | None = Field(
        None,
        description="ID модуля (NULL для общевузовских дисциплин и свободных элективов)",
    )
    cover_file_id: UUID | None = Field(
        None, description="ID файла обложки из таблицы files"
    )


class DisciplineUpdateRequest(BaseModel):
    title: str | None = Field(
        None, max_length=255, description="Название курса/предмета"
    )
    discipline_type: DisciplineType | None = Field(None, description="Тип дисциплины")
    status: DisciplineStatus | None = Field(None, description="Статус курса")
    description: str | None = Field(None, description="Описание курса")
    cover_file_id: UUID | None = Field(None, description="ID обложки курса")
    ends_at: date | None = Field(None, description="Дата окончания курса")

    @field_validator("title", "discipline_type", "status", mode="before")
    @classmethod
    def required_value(cls, value):
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError("Поле не может быть пустым")
        return value.strip() if isinstance(value, str) else value


class DisciplineResponse(DisciplineBase):
    id: UUID
    module_id: UUID | None
    author_id: UUID
    invite_code: str
    cover_file_id: UUID | None
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 3. СХЕМЫ ПОЛЬЗОВАТЕЛЕЙ (Таблица users)
# ==============================================================================

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserRegister(BaseModel):
    """Public registration input, including password confirmation."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "email": "student@example.com",
                    "first_name": "Анна",
                    "last_name": "Иванова",
                    "password": "ExamplePass123",
                    "password_confirm": "ExamplePass123",
                }
            ]
        },
    )

    email: EmailStr = Field(max_length=255)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=64)
    password_confirm: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_password(self) -> "UserRegister":
        password = self.password
        if not any(char.isupper() for char in password):
            raise ValueError("Пароль должен содержать хотя бы одну заглавную букву")
        if not any(char.isdigit() for char in password):
            raise ValueError("Пароль должен содержать хотя бы одну цифру")
        if password != self.password_confirm:
            raise ValueError("Пароли не совпадают")

        return self


class UserCreate(BaseModel):
    """Database input. Store only a securely generated password hash."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=255)
    password_hash: str = Field(min_length=1, max_length=255)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip()
        if not _EMAIL_RE.fullmatch(value):
            raise ValueError("Введите корректный адрес электронной почты")
        return value


class UserUpdate(BaseModel):
    """Fields that may be changed; a raw password is never accepted here."""

    model_config = ConfigDict(extra="forbid")

    email: str | None = Field(default=None, min_length=3, max_length=255)
    password_hash: str | None = Field(default=None, min_length=1, max_length=255)
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not _EMAIL_RE.fullmatch(value):
            raise ValueError("Введите корректный адрес электронной почты")
        return value

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "UserUpdate":
        for field_name in ("email", "password_hash", "first_name", "last_name"):
            if (
                field_name in self.model_fields_set
                and getattr(self, field_name) is None
            ):
                raise ValueError(f"Поле {field_name} не может быть пустым")
        return self


class UserPublicBase(BaseModel):
    """Публичные поля пользователя, общие для регистрации и профиля."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    first_name: str
    last_name: str
    is_active: bool
    created_at: datetime


class UserResponse(UserPublicBase):
    """Безопасное представление пользователя без password_hash и yandex_id."""

    updated_at: datetime | None = None


class UserProfileResponse(UserResponse):
    middle_name: str | None
    avatar_id: UUID | None
    is_admin: bool


# ==============================================================================
# 4. СХЕМЫ КОМАНД (Таблица teams)
# ==============================================================================


class TeamBase(BaseModel):
    name: str = Field(..., max_length=100, description="Название команды")
    description: str | None = Field(
        None, description="Описание командного проекта / тема"
    )


class TeamCreateRequest(TeamBase):
    discipline_id: UUID = Field(..., description="К какому курсу относится команда")


class TeamUpdateRequest(BaseModel):
    name: str | None = Field(None, max_length=100)
    description: str | None = None


class TeamResponse(TeamBase):
    id: UUID
    discipline_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 5. СХЕМЫ УЧАСТНИКОВ КУРСА (Таблица discipline_members)
# ==============================================================================

MemberRole = Literal["owner", "teacher", "student"]
MemberStatus = Literal["active", "invited", "left"]


class DisciplineMemberBase(BaseModel):
    role: MemberRole = Field(
        default="student", description="Роль: owner | teacher | student"
    )
    status: MemberStatus = Field(
        default="active", description="Статус: active | invited | left"
    )
    team_id: UUID | None = Field(
        None, description="В какой команде состоит студент на этом курсе"
    )


class DisciplineMemberCreateRequest(DisciplineMemberBase):
    discipline_id: UUID = Field(..., description="ID курса")
    user_id: UUID = Field(..., description="ID пользователя")


class DisciplineMemberUpdateRequest(BaseModel):
    role: MemberRole | None = None
    status: MemberStatus | None = None
    team_id: UUID | None = None


class DisciplineMemberResponse(DisciplineMemberBase):
    id: UUID
    discipline_id: UUID
    user_id: UUID
    enrolled_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DisciplineMemberProfileResponse(DisciplineMemberResponse):
    """Расширенный профиль участника с контактными данными из users (для раздела Контакты)."""

    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    avatar_id: UUID | None = None


# ==============================================================================
# 6. СХЕМЫ УРОКОВ (Таблица lessons)
# ==============================================================================


class LessonBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Тема занятия")
    order_index: int = Field(default=0, description="Порядковый номер занятия")
    content_markdown: str | None = Field(None, description="Конспект лекции в Markdown")
    is_published: bool = Field(default=True, description="Опубликован ли урок")


class LessonCreateRequest(LessonBase):
    discipline_id: UUID = Field(..., description="К какому курсу относится урок")


class LessonUpdateRequest(BaseModel):
    title: str | None = Field(None, max_length=255)
    order_index: int | None = None
    content_markdown: str | None = None
    is_published: bool | None = None


class LessonResponse(LessonBase):
    created_by: UUID | None = None
    id: UUID
    discipline_id: UUID
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 7. СХЕМЫ ЗАДАНИЙ (Таблица assignments)
# ==============================================================================

AssignmentTargetType = Literal["all", "selective"]


class AssignmentBase(BaseModel):
    title: str = Field(
        ..., min_length=1, max_length=255, description="Название задания / лабораторной"
    )
    description_markdown: str = Field(..., description="ТЗ и требования в Markdown")
    target_type: AssignmentTargetType = Field(
        default="all", description="all (всем) | selective (выборочно)"
    )
    is_team_work: bool = Field(
        default=False, description="Командное задание (True) или индивидуальное (False)"
    )
    max_score: int = Field(default=100, gt=0, description="Максимальный балл (> 0)")
    due_date: datetime | None = Field(None, description="Дедлайн сдачи")
    template_file_id: UUID | None = Field(
        None, description="Шаблон / методичка из files"
    )
    is_published: bool = Field(default=True, description="Опубликовано ли задание")


class AssignmentCreateRequest(AssignmentBase):
    lesson_id: UUID = Field(..., description="К какому уроку привязано задание")
    student_ids: list[UUID] | None = Field(
        default=None,
        description="Список ID студентов (user_id или member_id) для назначения при target_type='selective'",
    )

    @model_validator(mode="before")
    @classmethod
    def check_student_ids_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "student_ids" not in data:
                if "target_student_ids" in data:
                    data["student_ids"] = data["target_student_ids"]
                elif "member_ids" in data:
                    data["student_ids"] = data["member_ids"]
        return data


class AssignmentUpdateRequest(BaseModel):
    title: str | None = Field(None, max_length=255)
    description_markdown: str | None = None
    target_type: AssignmentTargetType | None = None
    is_team_work: bool | None = None
    max_score: int | None = Field(None, gt=0)
    due_date: datetime | None = None
    template_file_id: UUID | None = None
    is_published: bool | None = None
    student_ids: list[UUID] | None = Field(
        default=None,
        description="Список ID студентов (user_id или member_id) для назначения при target_type='selective'",
    )

    @model_validator(mode="before")
    @classmethod
    def check_student_ids_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "student_ids" not in data:
                if "target_student_ids" in data:
                    data["student_ids"] = data["target_student_ids"]
                elif "member_ids" in data:
                    data["student_ids"] = data["member_ids"]
        return data


class AssignmentResponse(AssignmentBase):
    created_by: UUID | None = None
    id: UUID
    lesson_id: UUID
    created_at: datetime
    updated_at: datetime | None = None
    student_ids: list[UUID] | None = Field(
        default=None,
        description="Список ID студентов, которым персонально назначено задание",
    )

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 8. СХЕМЫ ПЕРСОНАЛЬНОЙ ВЫДАЧИ ЗАДАНИЙ (Таблица assignment_targets)
# ==============================================================================


class AssignmentTargetCreateRequest(BaseModel):
    assignment_id: UUID = Field(..., description="ID задания")
    member_id: UUID = Field(..., description="ID участника курса (discipline_members)")


class AssignmentTargetResponse(BaseModel):
    id: UUID
    assignment_id: UUID
    member_id: UUID
    assigned_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 9. СХЕМЫ СДАЧИ ЗАДАНИЙ И ОЦЕНИВАНИЯ (Таблица submissions)
# ==============================================================================

SubmissionStatus = Literal["draft", "submitted", "in_review", "graded", "returned"]


class SubmissionCreateRequest(BaseModel):
    file_ids: list[UUID] = Field(default_factory=list, max_length=20)
    assignment_id: UUID = Field(..., description="ID задания")
    team_id: UUID | None = Field(
        None, description="Команда (если задание командное, иначе NULL)"
    )
    submitted_by: UUID = Field(
        ..., description="Студент, который физически отправил работу"
    )
    answer_text: str | None = Field(
        None, description="Текстовый ответ / комментарий к сдаче"
    )
    status: SubmissionStatus = Field(default="submitted", description="Статус сдачи")


class SubmissionUpdateRequest(BaseModel):
    file_ids: list[UUID] = Field(default_factory=list, max_length=20)
    answer_text: str | None = None
    status: SubmissionStatus | None = None


class SubmissionReviewRequest(BaseModel):
    """Оценивание работы или возврат на доработку преподавателем."""

    status: Literal["graded", "returned"] = Field(
        ..., description="graded (оценено) | returned (на доработку)"
    )
    score: float | None = Field(
        None, ge=0, description="Итоговый балл (обязателен при status='graded')"
    )
    feedback: str | None = Field(
        None, description="Рецензия / разбор ошибок преподавателем"
    )
    grader_id: UUID = Field(..., description="Преподаватель, выставивший оценку")


class SubmissionResponse(BaseModel):
    id: UUID
    assignment_id: UUID
    team_id: UUID | None
    submitted_by: UUID
    status: SubmissionStatus
    attempt_number: int
    answer_text: str | None
    submitted_at: datetime
    is_late: bool
    updated_at: datetime | None
    score: float | None
    feedback: str | None
    grader_id: UUID | None
    graded_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 10. СХЕМЫ ФАЙЛОВ И РЕСУРСОВ (Таблица files)
# ==============================================================================

FileType = Literal["link", "document", "video", "image", "archive"]


class FileBase(BaseModel):
    file_type: FileType = Field(
        ..., description="Тип: link | document | video | image | archive"
    )
    url: str = Field(
        ...,
        max_length=1024,
        description="Единый URL: S3, Яндекс.Документ, YouTube или внешняя ссылка",
    )
    file_name: str | None = Field(
        None, max_length=255, description="Оригинальное имя файла или заголовок ссылки"
    )
    size_bytes: int | None = Field(
        None, description="Размер в байтах (NULL для внешних ссылок)"
    )
    mime_type: str | None = Field(None, max_length=128, description="MIME-тип")
    meta: dict[str, Any] | None = Field(
        None, description="Технические метаданные S3 / API"
    )


class FileCreateRequest(FileBase):
    uploader_id: UUID | None = Field(None, description="Кто загрузил / добавил ссылку")
    lesson_id: UUID | None = Field(
        None, description="Урок, к которому прикреплён материал"
    )
    submission_id: UUID | None = Field(
        None, description="Сдача, к которой прикреплён файл"
    )


class FileResponse(FileBase):
    id: UUID
    uploader_id: UUID | None
    lesson_id: UUID | None
    submission_id: UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
