"""Модели публичного API; общие поля переиспользуются из schemas.data."""

from typing import Literal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, field_validator

from backend.schemas.data import (
    DisciplineBase, MemberRole, ModuleBase, UserProfileResponse, UserPublicBase,
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
