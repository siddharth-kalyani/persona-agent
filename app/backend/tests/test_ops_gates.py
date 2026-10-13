"""Bootstrap as a non-superuser (like the Aurora master user) and the onboarding content gate."""

from __future__ import annotations

import uuid

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import ADMIN_URL, TENANT
from vanimo.db.session import provision_user, user_tx
from vanimo.gates import ReviewPending, require_review_done
from vanimo.ops.bootstrap_db import bootstrap

pytestmark = pytest.mark.db


def test_bootstrap_twice_as_non_superuser() -> None:
    suffix = uuid.uuid4().hex[:8]
    admin, owner, app, db = f"ci_admin_{suffix}", f"ci_owner_{suffix}", f"ci_app_{suffix}", f"ci_db_{suffix}"
    with psycopg.connect(ADMIN_URL, autocommit=True) as conn:
        conn.execute(f"create role \"{admin}\" login password 'pw' createrole createdb")
    admin_url = psycopg.conninfo.make_conninfo(ADMIN_URL, user=admin, password="pw")
    try:
        for _ in range(2):  # the second run takes the "role exists" path that broke on Aurora
            bootstrap(admin_url, db, "owner_pw", "app_pw", owner=owner, app=app)
        with psycopg.connect(ADMIN_URL) as conn:
            rows = conn.execute(
                "select rolname, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb from pg_roles "
                "where rolname = any(%s)",
                ([owner, app],),
            ).fetchall()
        assert sorted(rows) == sorted([(owner, False, False, False, False), (app, False, False, False, False)])
    finally:
        with psycopg.connect(ADMIN_URL, autocommit=True) as conn:
            conn.execute(f'drop database if exists "{db}" with (force)')
            for role in (app, owner, admin):
                conn.execute(f'drop role if exists "{role}"')


async def test_content_gate(database: dict[str, str]) -> None:
    engine = create_async_engine(database["app"])
    ref = await provision_user(engine, entra_tenant_id=TENANT, entra_oid=str(uuid.uuid4()), cell="in", data_region="IN")
    with pytest.raises(ReviewPending):
        await require_review_done(engine, ref, "sample")
    async with user_tx(engine, ref) as conn:
        await conn.execute(
            text(
                "update vanimo.users set onboarding_state = 'review_done', review_outcome = 'skipped', "
                "review_completed_at = now(), reviewed_sources = '{sample}'"
            )
        )
    await require_review_done(engine, ref, "sample")
    # Reviewing the sample workspace never unlocks a real mailbox.
    with pytest.raises(ReviewPending):
        await require_review_done(engine, ref, "graph")
    await engine.dispose()


async def test_new_functions_are_not_executable_by_public(database: dict[str, str]) -> None:
    """Default privileges: a function a later migration forgets to lock down stays unusable by the API."""
    owner = psycopg.connect(database["owner"].replace("postgresql+psycopg://", "postgresql://"))
    try:
        with owner.cursor() as cur:
            cur.execute(
                "create function vanimo_private.probe_fn() returns int language sql security definer "
                "set search_path = vanimo, pg_temp as $$ select 1 $$"
            )
            cur.execute("select has_function_privilege('vanimo_app', 'vanimo_private.probe_fn()', 'execute')")
            assert cur.fetchone() == (False,)
    finally:
        owner.rollback()
        owner.close()
