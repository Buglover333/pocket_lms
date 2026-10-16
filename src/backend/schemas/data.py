from datetime import date, datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


# ==============================================================================
# 1. СХЕМЫ МОДУЛЕЙ (Таблица modules)
# ==============================================================================

class ModuleBase(BaseModel):
    title: str = Field(..., max_length=255, description="Название образовательного модуля")
    description: str | None = Field(None, description="Описание программы модуля")


class ModuleCreate(ModuleBase):
    curator_id: UUID = Field(..., description="ID пользователя-куратора модуля")


class ModuleUpdate(BaseModel):
    title: str | None = Field(None, max_length=255, description="Название образовательного модуля")
    description: str | None = Field(None, description="Описание программы модуля")
    curator_id: UUID | None = Field(None, description="ID пользователя-куратора модуля")


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
    title: str = Field(..., max_length=255, description="Название курса/предмета")
    discipline_type: DisciplineType = Field(default="module", description="Тип: модуль программы, общевузовский, электив")
    status: DisciplineStatus = Field(default="draft", description="Статус: черновик, опубликован, архив")
    description: str | None = Field(None, description="Описание курса и требований")
    ends_at: date | None = Field(None, description="Дата окончания курса для авто-архивации")


class DisciplineCreate(DisciplineBase):
    author_id: UUID = Field(..., description="ID создателя курса (защита от курсов-сирот)")
    invite_code: str = Field(..., max_length=32, description="Уникальный код для записи на курс")
    module_id: UUID | None = Field(None, description="ID модуля (NULL для общевузовских дисциплин и свободных элективов)")
    cover_file_id: UUID | None = Field(None, description="ID файла обложки из таблицы files")


class DisciplineUpdate(BaseModel):
    title: str | None = Field(None, max_length=255, description="Название курса/предмета")
    discipline_type: DisciplineType | None = Field(None, description="Тип дисциплины")
    status: DisciplineStatus | None = Field(None, description="Статус курса")
    description: str | None = Field(None, description="Описание курса")
    cover_file_id: UUID | None = Field(None, description="ID обложки курса")
    ends_at: date | None = Field(None, description="Дата окончания курса")


class DisciplineResponse(DisciplineBase):
    id: UUID
    module_id: UUID | None
    author_id: UUID
    invite_code: str
    cover_file_id: UUID | None
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)