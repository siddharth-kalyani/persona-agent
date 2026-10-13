"""Alembic runs as `vanimo_owner` (VANIMO_DB_OWNER_URL), never as the API's role."""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine, pool, text


def _url() -> str:
    url = os.environ.get("VANIMO_DB_OWNER_URL")
    if not url:
        raise RuntimeError("set VANIMO_DB_OWNER_URL (postgresql+psycopg://vanimo_owner:...@host:port/vanimo)")
    return url


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as conn:
        conn.execute(text("set search_path = vanimo, pg_temp"))
        context.configure(connection=conn, version_table_schema="vanimo", transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()
        conn.commit()


if context.is_offline_mode():
    raise RuntimeError("offline migrations are not supported")
run_migrations_online()
