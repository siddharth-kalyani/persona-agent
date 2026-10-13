"""One-shot database setup for a deployed cell: bootstrap roles, then run migrations.

Runs as an ECS task with the database credentials injected from Secrets Manager:
  VANIMO_DB_HOST, VANIMO_DB_PORT, VANIMO_DB_NAME
  VANIMO_DB_ADMIN_USER, VANIMO_DB_ADMIN_PASSWORD   (cluster master secret)
  VANIMO_DB_OWNER_PASSWORD, VANIMO_DB_APP_PASSWORD (generated secrets)

    python -m vanimo.ops.migrate
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

from alembic import command
from alembic.config import Config

from vanimo.ops.bootstrap_db import OWNER, bootstrap

BACKEND = Path(__file__).resolve().parents[2]


def _url(driver: str, user: str, password: str, host: str, port: str, db: str) -> str:
    return f"{driver}://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}/{db}?sslmode=require"


def main() -> None:
    env = os.environ
    host, port, db = env["VANIMO_DB_HOST"], env.get("VANIMO_DB_PORT", "5432"), env.get("VANIMO_DB_NAME", "vanimo")
    owner_pw = env["VANIMO_DB_OWNER_PASSWORD"]
    bootstrap(
        admin_url=_url(
            "postgresql", env["VANIMO_DB_ADMIN_USER"], env["VANIMO_DB_ADMIN_PASSWORD"], host, port, "postgres"
        ),
        db_name=db,
        owner_password=owner_pw,
        app_password=env["VANIMO_DB_APP_PASSWORD"],
    )
    os.environ["VANIMO_DB_OWNER_URL"] = _url("postgresql+psycopg", OWNER, owner_pw, host, port, db)
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    print("migrate.ok")


if __name__ == "__main__":
    main()
