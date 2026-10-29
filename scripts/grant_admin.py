"""Offline developer-only initial provisioning. Never exposed as an HTTP endpoint."""

import argparse
import os

import psycopg

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Назначить администратором существующий аккаунт разработчика"
    )
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("Set DATABASE_URL first")
    with psycopg.connect(url) as conn:
        row = conn.execute(
            "UPDATE users SET is_admin=true,updated_at=now() WHERE lower(email)=lower(%s) AND is_active RETURNING id",
            (args.email,),
        ).fetchone()
        if row is None:
            raise SystemExit("Активный аккаунт не найден; сначала зарегистрируйтесь")
        conn.execute(
            "INSERT INTO security_events(actor_id,action,subject_id) VALUES (%s,'admin_provisioned_offline',%s)",
            (row[0], row[0]),
        )
        print("Admin provisioned:", row[0])
