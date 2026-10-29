"""Apply schema / pending migrations atomically. Reads DATABASE_URL; never prints it."""

import hashlib
import os
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]


def migrate(url):
    with psycopg.connect(url) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(732946173)")
        fresh = conn.execute("SELECT to_regclass('public.users')").fetchone()[0] is None
        if fresh:
            conn.execute((ROOT / "src/backend/db/schemas.sql").read_text())
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations(name TEXT PRIMARY KEY, checksum TEXT NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        for path in sorted((ROOT / "src/backend/db/migrations").glob("*.sql")):
            source = path.read_text()
            checksum = hashlib.sha256(source.encode()).hexdigest()
            row = conn.execute(
                "SELECT checksum FROM schema_migrations WHERE name=%s", (path.name,)
            ).fetchone()
            if row:
                if row[0] != checksum:
                    raise RuntimeError("Изменилась применённая миграция: " + path.name)
                continue
            conn.execute(source)
            conn.execute(
                "INSERT INTO schema_migrations(name,checksum) VALUES (%s,%s)",
                (path.name, checksum),
            )
            print("Applied:", path.name)


if __name__ == "__main__":
    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("Set DATABASE_URL first")
    migrate(url)
