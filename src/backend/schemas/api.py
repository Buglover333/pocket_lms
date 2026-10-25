"""Модели публичного API; общие поля переиспользуются из schemas.data."""

from typing import Literal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, field_validator

from backend.schemas.data import (
    DisciplineBase, MemberRole, ModuleBase, UserProfileResponse, UserPublicBase,
    SubmissionReviewRequest,
)


class ErrorResponse(BaseModel):
    detail: str


class AuthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

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


RegisterResponse = UserPublicBase
UserInfoResponse = UserProfileResponse


class CourseItem(DisciplineBase):
    id: UUID
    module_id: UUID | None
    author_id: UUID
    cover_file_id: UUID | None
    role: MemberRole = Field(validation_alias=AliasChoices("role", "member_role"))
    team_id: UUID | None


class CoursesResponse(BaseModel):
    items: list[CourseItem]


class ModuleItem(ModuleBase):
    id: UUID
    curator_id: UUID


class ModulesResponse(BaseModel):
    items: list[ModuleItem]


class ProfileSettingsUpdate(BaseModel):
    """Public self-service fields. Internal UserUpdate also supports password hashes."""
    model_config = ConfigDict(extra="forbid")
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def clean_name(cls, value):
        if value is None:
            raise ValueError("Имя и фамилия не могут быть пустыми")
        return value.strip() if isinstance(value, str) else value


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


from backend.schemas.data import LessonResponse, FileResponse, SubmissionResponse

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
