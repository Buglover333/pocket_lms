"""Модели публичного API; общие поля переиспользуются из schemas.data."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from backend.schemas.data import (
    AssignmentResponse,
    AssignmentTargetResponse,
    DisciplineBase,
    DisciplineResponse,
    MemberRole,
    MemberStatus,
    ModuleResponse,
    SubmissionReviewRequest,
    SubmissionStatus,
    UserProfileResponse,
    UserPublicBase,
    UserResponse,
)


class ErrorResponse(BaseModel):
    detail: str


class AuthRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [{"email": "student@mail.ru", "password": "ExamplePass123"}]
        },
    )

    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=1, max_length=64)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user_id: UUID
    session_id: UUID
    expires_in: int = 900


RegisterResponse = UserPublicBase
UserInfoResponse = UserProfileResponse


class CourseItem(DisciplineResponse):
    role: MemberRole | None = Field(
        default=None, validation_alias=AliasChoices("role", "member_role")
    )
    team_id: UUID | None = None


class CourseCreateRequest(DisciplineBase):
    model_config = ConfigDict(extra="forbid")
    status: Literal["draft", "published"]
    author_id: UUID
    module_id: UUID | None = None
    cover_file_id: UUID | None = None


class CourseCreatedResponse(DisciplineResponse):
    invite_code: str = Field(
        description="Legacy-код генерируется сервером; для вступления используйте create_invitation"
    )


class ModuleDataResponse(ModuleResponse):
    disciplines: list[DisciplineResponse]


class CourseMemberResponse(UserResponse):
    user_id: UUID
    member_id: UUID
    discipline_id: UUID
    role: MemberRole
    status: MemberStatus
    team_id: UUID | None = None
    middle_name: str | None = None
    avatar_id: UUID | None = None
    enrolled_at: datetime


class AssignmentTargetProfileResponse(AssignmentTargetResponse):
    user_id: UUID
    first_name: str
    last_name: str
    email: str


class AssignmentDataResponse(BaseModel):
    assignment: AssignmentResponse
    targets: list[AssignmentTargetProfileResponse]


class GradeResponse(BaseModel):
    assignment_id: UUID
    assignment_title: str
    max_score: int = Field(gt=0)
    due_date: datetime | None
    submission_id: UUID | None
    status: SubmissionStatus | None
    score: float | None = Field(ge=0, allow_inf_nan=False)
    feedback: str | None
    graded_at: datetime | None
    attempt_number: int | None = Field(ge=1)

    @model_validator(mode="after")
    def check_grade(self):
        if self.score is not None and self.score > self.max_score:
            raise ValueError("Оценка превышает максимум задания")
        if self.submission_id is None and any(
            v is not None
            for v in (
                self.status,
                self.score,
                self.feedback,
                self.graded_at,
                self.attempt_number,
            )
        ):
            raise ValueError("Данные сдачи отсутствуют")
        return self


class ProfileSettingsUpdate(BaseModel):
    """Public self-service fields. Internal UserUpdate also supports password hashes."""

    model_config = ConfigDict(extra="forbid")
    middle_name: str | None = Field(default=None, max_length=100)
    avatar_id: UUID | None = None
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def clean_name(cls, value):
        if value is None:
            raise ValueError("Имя и фамилия не могут быть пустыми")
        return value.strip() if isinstance(value, str) else value

    @field_validator("middle_name", mode="before")
    @classmethod
    def clean_middle_name(cls, value):
        return value.strip() or None if isinstance(value, str) else value


class DeleteAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=64)


class GradeSubmissionRequest(SubmissionReviewRequest):
    """Оценивание; возврат выполняется отдельным /return_submission."""

    model_config = ConfigDict(extra="forbid")
    status: Literal["graded"] = "graded"
    score: float = Field(ge=0, allow_inf_nan=False)


class FileUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_name: str = Field(min_length=1, max_length=255)
    file_type: Literal["document", "video", "image", "archive"]
    mime_type: str = Field(min_length=3, max_length=128, pattern=r"^[\w.+-]+/[\w.+-]+$")
    size_bytes: int = Field(gt=0, le=50 * 1024 * 1024)
    lesson_id: UUID | None = None
    submission_id: UUID | None = None


from backend.schemas.data import FileResponse, LessonResponse, SubmissionResponse


class MaterialDataResponse(BaseModel):
    material: LessonResponse
    files: list[FileResponse]


class MaterialsResponse(BaseModel):
    items: list[LessonResponse]


class SubmissionsResponse(BaseModel):
    items: list[SubmissionResponse]


class SubmissionDataResponse(BaseModel):
    submission: SubmissionResponse
    files: list[FileResponse]


class FileUploadResponse(BaseModel):
    file_id: UUID
    upload_url: str
    fields: dict[str, str]
    expires_in: int


class FileDownloadResponse(BaseModel):
    download_url: str
    expires_in: int | None
