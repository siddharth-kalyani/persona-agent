"""Isolation canaries: one user can never see or write another user's rows."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from tests.conftest import OTHER_TENANT, TENANT
from vanimo import audit
from vanimo.db.session import UserRef, provision_user, user_tx

pytestmark = pytest.mark.db


@pytest.fixture
async def engine(database: dict[str, str]) -> AsyncEngine:
    eng = create_async_engine(database["app"])
    yield eng
    await eng.dispose()


async def _user(engine: AsyncEngine, tid: str = TENANT) -> UserRef:
    return await provision_user(engine, entra_tenant_id=tid, entra_oid=str(uuid.uuid4()), cell="in", data_region="IN")


async def test_provisioning_is_idempotent(engine: AsyncEngine) -> None:
    oid = str(uuid.uuid4())
    a = await provision_user(engine, entra_tenant_id=TENANT, entra_oid=oid, cell="in", data_region="IN")
    b = await provision_user(engine, entra_tenant_id=TENANT, entra_oid=oid, cell="in", data_region="IN")
    assert a == b


async def test_provisioning_rejects_non_guid(engine: AsyncEngine) -> None:
    with pytest.raises(DBAPIError):
        await provision_user(engine, entra_tenant_id="x' or 1=1", entra_oid="y", cell="in", data_region="IN")


async def test_users_see_only_their_own_rows(engine: AsyncEngine) -> None:
    alice, bob = await _user(engine), await _user(engine)
    carol = await _user(engine, OTHER_TENANT)
    canary = f"canary_{uuid.uuid4().hex[:12]}"
    for ref in (alice, bob, carol):
        async with user_tx(engine, ref) as conn:
            await audit.record(
                conn, ref, "canary.write", target_kind="canary", target_ref=f"{canary}_{ref.user_id.hex[:8]}"
            )

    for ref in (alice, bob, carol):
        async with user_tx(engine, ref) as conn:
            rows = (await conn.execute(text("select user_id, target_ref from vanimo.audit_events"))).all()
            users = (await conn.execute(text("select id from vanimo.users"))).scalars().all()
            tenants = (await conn.execute(text("select id from vanimo.tenants"))).scalars().all()
        assert {r.user_id for r in rows} == {ref.user_id}
        assert all(r.target_ref.endswith(ref.user_id.hex[:8]) for r in rows if r.target_ref.startswith(canary))
        assert users == [ref.user_id]
        assert tenants == [ref.tenant_id]


async def test_no_identity_sees_nothing(engine: AsyncEngine) -> None:
    await _user(engine)
    async with engine.connect() as conn:
        for table in ("tenants", "users", "audit_events"):
            assert (await conn.execute(text(f"select count(*) from vanimo.{table}"))).scalar_one() == 0  # noqa: S608


async def test_cannot_write_as_someone_else(engine: AsyncEngine) -> None:
    alice, bob = await _user(engine), await _user(engine)
    with pytest.raises(DBAPIError, match="row-level security"):
        async with user_tx(engine, alice) as conn:
            await audit.record(conn, bob, "canary.forged")


async def test_cross_tenant_write_blocked(engine: AsyncEngine) -> None:
    alice = await _user(engine)
    carol = await _user(engine, OTHER_TENANT)
    forged = UserRef(tenant_id=carol.tenant_id, user_id=alice.user_id)
    with pytest.raises(DBAPIError):
        async with user_tx(engine, alice) as conn:
            await audit.record(conn, forged, "canary.forged")


async def test_settings_do_not_leak_across_transactions(engine: AsyncEngine) -> None:
    alice = await _user(engine)
    async with user_tx(engine, alice):
        pass
    async with engine.connect() as conn:  # likely the same pooled connection
        assert (await conn.execute(text("select current_setting('app.user_id', true)"))).scalar_one() in (None, "")


async def test_app_role_cannot_escalate(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        role = (
            await conn.execute(
                text("select rolsuper, rolbypassrls, rolcreaterole from pg_roles where rolname = current_user")
            )
        ).one()
        assert tuple(role) == (False, False, False)
        owner = (
            await conn.execute(
                text("select tableowner from pg_tables where schemaname = 'vanimo' and tablename = 'users'")
            )
        ).scalar_one()
        assert owner == "vanimo_owner"
    for stmt in (
        "set role vanimo_owner",
        "alter table vanimo.users disable row level security",
        "delete from vanimo.audit_events",
        "update vanimo.users set entra_oid = 'x'",
        "create table vanimo.evil (id int)",
        "create table public.evil (id int)",
    ):
        async with engine.connect() as conn:
            with pytest.raises((ProgrammingError, DBAPIError)):
                await conn.execute(text(stmt))


async def test_rls_forced_on_every_table(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "select relname, relrowsecurity, relforcerowsecurity from pg_class c "
                    "join pg_namespace n on n.oid = c.relnamespace "
                    "where n.nspname = 'vanimo' and c.relkind = 'r' and relname <> 'alembic_version'"
                )
            )
        ).all()
    assert rows, "no tables found"
    assert all(r.relrowsecurity and r.relforcerowsecurity for r in rows), rows
