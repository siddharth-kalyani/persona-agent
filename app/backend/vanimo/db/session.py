"""Database access. Every user-data query runs inside `user_tx`, which pins the
transaction to one tenant and one user so row-level security does the filtering."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from vanimo.config import Settings


@dataclass(frozen=True)
class UserRef:
    tenant_id: uuid.UUID
    user_id: uuid.UUID


def make_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url.get_secret_value(),
        pool_size=settings.db_pool_size,
        pool_pre_ping=True,
        # Fail a request instead of hanging it when the database is unreachable.
        connect_args={"connect_timeout": settings.db_connect_timeout_s},
        # Statements and parameters are never logged (they may hold user data).
        echo=False,
        hide_parameters=True,
    )


@asynccontextmanager
async def user_tx(engine: AsyncEngine, ref: UserRef) -> AsyncIterator[AsyncConnection]:
    async with engine.begin() as conn:
        # Transaction-local (is_local = true): settings vanish at commit/rollback, so a
        # pooled connection never carries one user's identity into another request.
        await conn.execute(
            text("select set_config('app.tenant_id', :t, true), set_config('app.user_id', :u, true)"),
            {"t": str(ref.tenant_id), "u": str(ref.user_id)},
        )
        yield conn


async def provision_user(
    engine: AsyncEngine, *, entra_tenant_id: str, entra_oid: str, cell: str, data_region: str
) -> UserRef:
    async with engine.begin() as conn:
        row = (
            await conn.execute(
                text("select tenant_id, user_id from vanimo_private.provision_user(:tid, :oid, :cell, :region)"),
                {"tid": entra_tenant_id, "oid": entra_oid, "cell": cell, "region": data_region},
            )
        ).one()
    return UserRef(tenant_id=row.tenant_id, user_id=row.user_id)
