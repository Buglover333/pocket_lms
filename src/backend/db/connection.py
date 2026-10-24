"""Подключение к PostgreSQL и транзакция без зависимости от HTTP-слоя."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import psycopg
from psycopg.rows import dict_row


class DatabaseConfigurationError(RuntimeError):
    pass


@asynccontextmanager
async def connection() -> AsyncIterator[psycopg.AsyncConnection]:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise DatabaseConfigurationError("DATABASE_URL не настроен")
    async with await psycopg.AsyncConnection.connect(url, row_factory=dict_row) as conn:
        yield conn
