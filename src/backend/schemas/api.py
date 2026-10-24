"""Public request and response models from API_DESCRIPTION.md."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from backend.schemas.data import DisciplineStatus, DisciplineType


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


class RegisterResponse(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    is_active: bool
    created_at: datetime


class UserInfoResponse(RegisterResponse):
    middle_name: str | None
    avatar_id: UUID | None
    is_admin: bool
    updated_at: datetime | None


class CourseItem(BaseModel):
    id: UUID
    module_id: UUID | None
    author_id: UUID
    title: str
    discipline_type: DisciplineType
    status: DisciplineStatus
    description: str | None
    cover_file_id: UUID | None
    ends_at: date | None
    role: Literal["owner", "teacher", "student"]
    team_id: UUID | None


class CoursesResponse(BaseModel):
    items: list[CourseItem]


class ModuleItem(BaseModel):
    id: UUID
    title: str
    description: str | None
    curator_id: UUID


class ModulesResponse(BaseModel):
    items: list[ModuleItem]
