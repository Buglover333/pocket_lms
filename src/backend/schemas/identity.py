"""Public identity contracts: role and creator identity cannot be supplied at registration."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NewPassword(StrictModel):
    password: str = Field(min_length=8, max_length=64)
    password_confirm: str = Field(max_length=64)

    @model_validator(mode="after")
    def validate_password(self):
        if self.password != self.password_confirm:
            raise ValueError("Пароли не совпадают")
        if not any(x.isupper() for x in self.password) or not any(
            x.isdigit() for x in self.password
        ):
            raise ValueError("Пароль должен содержать заглавную букву и цифру")
        return self


class ChangePassword(NewPassword):
    current_password: str = Field(min_length=1, max_length=64)


class ResetPassword(NewPassword):
    reset_code: str = Field(min_length=32, max_length=128)


class BlockAccount(StrictModel):
    blocked: bool


class InvitationCreate(StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "course_id": "00000000-0000-4000-8000-000000000001",
                    "role": "student",
                    "expires_in_days": 7,
                    "max_uses": 100,
                }
            ]
        },
    )
    course_id: UUID | None = None
    module_id: UUID | None = None
    course_ids: list[UUID] = Field(default_factory=list, max_length=100)
    role: Literal["student", "teacher"] = "student"
    expires_in_days: int = Field(default=7, ge=1, le=30)
    max_uses: int = Field(default=100, ge=1, le=1000)

    @model_validator(mode="after")
    def scope(self):
        if bool(self.course_id) == bool(self.module_id):
            raise ValueError("Укажите либо course_id, либо module_id")
        if self.module_id and not self.course_ids:
            raise ValueError("Выберите хотя бы один курс модуля")
        if self.course_id and self.course_ids:
            raise ValueError("course_ids используется только с module_id")
        self.course_ids = list(dict.fromkeys(self.course_ids))
        return self


class InvitationResponse(BaseModel):
    id: UUID
    module_id: UUID | None
    course_ids: list[UUID]
    role: Literal["student", "teacher"]
    expires_at: datetime
    max_uses: int
    invite_code: str
    invitation_url: str


class DeviceSession(BaseModel):
    id: UUID
    device_name: str
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    current: bool


class SessionList(BaseModel):
    items: list[DeviceSession]


class ResetCodeResponse(BaseModel):
    reset_code: str
    expires_at: datetime


class AccountStatusResponse(BaseModel):
    id: UUID
    is_active: bool


class SuccessResponse(BaseModel):
    ok: Literal[True]


class MessageResponse(SuccessResponse):
    detail: str


class InvitationAcceptance(BaseModel):
    invitation_id: UUID
    module_id: UUID | None
    course_ids: list[UUID]
    role: Literal["student", "teacher"]
    already_accepted: bool
