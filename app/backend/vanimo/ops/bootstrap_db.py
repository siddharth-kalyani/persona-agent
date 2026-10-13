"""Create the database and its two roles. Idempotent; run with an admin connection.

  vanimo_owner  owns the schema and runs migrations (never used by the API)
  vanimo_app    what the API connects as: not an owner, NOBYPASSRLS, so row-level
                security always applies

The admin does not have to be a true superuser: on Aurora/RDS the master user only has
CREATEROLE + CREATEDB (rds_superuser). Since PostgreSQL 16 such a role may not even
*mention* SUPERUSER/BYPASSRLS in ALTER ROLE, so existing roles only get their password
reset, and their attributes are verified instead of re-set.

Usage:
  python -m vanimo.ops.bootstrap_db
Environment:
  VANIMO_DB_ADMIN_URL      postgresql://postgres:...@host:port/postgres
  VANIMO_DB_NAME           default "vanimo"
  VANIMO_DB_OWNER_PASSWORD / VANIMO_DB_APP_PASSWORD
"""

from __future__ import annotations

import os

import psycopg
from psycopg import sql

OWNER = "vanimo_owner"
APP = "vanimo_app"


class UnsafeRoleError(RuntimeError):
    pass


def _ensure_role(cur: psycopg.Cursor, role: str, password: str) -> None:
    cur.execute("select 1 from pg_roles where rolname = %s", (role,))
    if cur.fetchone():
        cur.execute(sql.SQL("alter role {} with login password {}").format(sql.Identifier(role), sql.Literal(password)))
    else:
        # A role created by a non-superuser can never be SUPERUSER or BYPASSRLS; say so explicitly anyway.
        cur.execute(
            sql.SQL("create role {} with login password {} nosuperuser nocreatedb nocreaterole nobypassrls").format(
                sql.Identifier(role), sql.Literal(password)
            )
        )
    cur.execute("select rolsuper, rolbypassrls, rolcreaterole, rolcreatedb from pg_roles where rolname = %s", (role,))
    attrs = cur.fetchone()
    if attrs is None or any(attrs):
        raise UnsafeRoleError(f"role {role} must not be superuser/bypassrls/createrole/createdb: {attrs}")


def bootstrap(
    admin_url: str,
    db_name: str,
    owner_password: str,
    app_password: str,
    *,
    owner: str = OWNER,
    app: str = APP,
) -> None:
    with psycopg.connect(admin_url, autocommit=True) as conn, conn.cursor() as cur:
        _ensure_role(cur, owner, owner_password)
        _ensure_role(cur, app, app_password)
        # On RDS/Aurora the admin must be a member of the owner role to hand over ownership.
        cur.execute(sql.SQL("grant {} to current_user").format(sql.Identifier(owner)))
        cur.execute("select 1 from pg_database where datname = %s", (db_name,))
        if not cur.fetchone():
            cur.execute(sql.SQL("create database {} owner {}").format(sql.Identifier(db_name), sql.Identifier(owner)))

    db_url = psycopg.conninfo.make_conninfo(admin_url, dbname=db_name)
    with psycopg.connect(db_url, autocommit=True) as conn, conn.cursor() as cur:
        ident = sql.Identifier
        for stmt in (
            sql.SQL("revoke all on database {} from public").format(ident(db_name)),
            sql.SQL("revoke create on schema public from public"),
            sql.SQL("grant connect on database {} to {}").format(ident(db_name), ident(app)),
            sql.SQL("create schema if not exists vanimo authorization {}").format(ident(owner)),
            sql.SQL("create schema if not exists vanimo_private authorization {}").format(ident(owner)),
            sql.SQL("grant usage on schema vanimo to {}").format(ident(app)),
            sql.SQL("grant usage on schema vanimo_private to {}").format(ident(app)),
        ):
            cur.execute(stmt)
        for role in (owner, app):
            cur.execute(
                sql.SQL("alter role {} in database {} set search_path = vanimo, pg_temp").format(
                    ident(role), ident(db_name)
                )
            )


def main() -> None:
    bootstrap(
        admin_url=os.environ["VANIMO_DB_ADMIN_URL"],
        db_name=os.environ.get("VANIMO_DB_NAME", "vanimo"),
        owner_password=os.environ["VANIMO_DB_OWNER_PASSWORD"],
        app_password=os.environ["VANIMO_DB_APP_PASSWORD"],
    )
    print("bootstrap.ok")


if __name__ == "__main__":
    main()
