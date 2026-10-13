"""Operator script: create a local (email + password) account, or reset its password.

The super-admin console waits for external tenants (docs/03 §0), so accounts are made here.
A one-time password is printed once; the user must replace it at first sign-in.

    uv run python -m vanimo.ops.local_user --email someone@example.com --role superadmin
    uv run python -m vanimo.ops.local_user --email someone@example.com --reset

Runs as the schema owner (VANIMO_DB_OWNER_URL), like migrations.
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid

import psycopg

from vanimo.auth.entra import ROLE_ADMIN, ROLE_SUPERADMIN, ROLE_USER
from vanimo.auth.passwords import hash_password, new_one_time_password
from vanimo.config import Settings

ROLE_SETS = {
    "user": [ROLE_USER],
    "admin": [ROLE_USER, ROLE_ADMIN],
    "superadmin": [ROLE_USER, ROLE_ADMIN, ROLE_SUPERADMIN],
}
# Tenant key for local accounts when no Entra tenant is configured yet.
LOCAL_TENANT_KEY = "local"


def upsert_local_user(owner_url: str, email: str, role: str, *, reset: bool, settings: Settings) -> str:
    email = email.strip().lower()
    if "@" not in email:
        raise SystemExit("not an email address")
    one_time = new_one_time_password()
    pw_hash = hash_password(one_time)
    tenant_key = settings.entra_tenant_id or LOCAL_TENANT_KEY
    url = owner_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url) as conn, conn.transaction():
        conn.execute("set local search_path = vanimo, pg_temp")
        existing = conn.execute("select user_id from local_credentials where email = %s", (email,)).fetchone()
        if existing:
            if not reset:
                raise SystemExit(f"{email} already exists; use --reset to issue a new one-time password")
            conn.execute(
                "update local_credentials set password_hash = %s, must_change_password = true, "
                "failed_attempts = 0, locked_until = null, roles = %s where user_id = %s",
                (pw_hash, ROLE_SETS[role], existing[0]),
            )
            conn.execute("update sessions set revoked_at = now() where user_id = %s and revoked_at is null", existing)
            return one_time
        if reset:
            raise SystemExit(f"{email} doesn't exist; drop --reset to create it")
        conn.execute(
            "insert into tenants (entra_tenant_id, cell, data_region) values (%s, %s, %s) "
            "on conflict (entra_tenant_id) do nothing",
            (tenant_key, settings.cell, settings.cell_config.data_region),
        )
        tenant_id = conn.execute("select id from tenants where entra_tenant_id = %s", (tenant_key,)).fetchone()[0]
        # Local accounts have no Entra object ID; a unique placeholder keeps the column's meaning clear.
        user_id = conn.execute(
            "insert into users (tenant_id, entra_oid) values (%s, %s) returning id",
            (tenant_id, f"local:{uuid.uuid4()}"),
        ).fetchone()[0]
        conn.execute(
            "insert into local_credentials (user_id, email, password_hash, must_change_password, roles) "
            "values (%s, %s, %s, true, %s)",
            (user_id, email, pw_hash, ROLE_SETS[role]),
        )
    return one_time


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vanimo.ops.local_user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", choices=sorted(ROLE_SETS), default="user")
    parser.add_argument("--reset", action="store_true", help="issue a new one-time password (and set --role)")
    args = parser.parse_args(argv)
    owner_url = os.environ.get("VANIMO_DB_OWNER_URL")
    if not owner_url:
        raise SystemExit("set VANIMO_DB_OWNER_URL")
    one_time = upsert_local_user(owner_url, args.email, args.role, reset=args.reset, settings=Settings())
    print(f"{'Reset' if args.reset else 'Created'} {args.email.strip().lower()} ({args.role}).")
    print(f"One-time password (shown once; must be changed at first sign-in): {one_time}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
