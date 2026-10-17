import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserRegister(BaseModel):
    """Public registration input, including password confirmation."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=255)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=64)
    password_confirm: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip()
        if not _EMAIL_RE.fullmatch(value):
            raise ValueError("Введите корректный адрес электронной почты")
        return value

    @model_validator(mode="after")
    def validate_password(self) -> "UserRegister":
        password = self.password
        if not any(char.isupper() for char in password):
            raise ValueError("Пароль должен содержать хотя бы одну заглавную букву")
        if not any(char.isdigit() for char in password):
            raise ValueError("Пароль должен содержать хотя бы одну цифру")
        if password != self.password_confirm:
            raise ValueError("Пароли не совпадают")

        personal_values = [self.email, self.email.split("@", 1)[0], self.first_name, self.last_name]
        normalized_password = password.casefold()
        if any(value and normalized_password == value.strip().casefold() for value in personal_values):
            raise ValueError("Пароль не должен совпадать с именем или электронной почтой")
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
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"Поле {field_name} не может быть пустым")
        return self


class UserResponse(BaseModel):
    """Safe user representation; deliberately excludes password_hash."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    first_name: str
    last_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
