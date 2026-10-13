"""Content-free audit events: an action, a kind and an opaque reference — never content."""

from __future__ import annotations

import hashlib
import hmac

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from vanimo.db.session import UserRef


def opaque_ref(key: str, value: str) -> str:
    """Stable keyed hash of an identifier (HMAC-SHA256, hex, 32 chars)."""
    return hmac.new(key.encode(), value.encode(), hashlib.sha256).hexdigest()[:32]


async def record(
    conn: AsyncConnection,
    ref: UserRef,
    action: str,
    *,
    target_kind: str | None = None,
    target_ref: str | None = None,
    request_id: str | None = None,
) -> None:
    await conn.execute(
        text(
            "insert into vanimo.audit_events (tenant_id, user_id, action, target_kind, target_ref, request_id) "
            "values (:t, :u, :a, :k, :r, :q)"
        ),
        {"t": ref.tenant_id, "u": ref.user_id, "a": action, "k": target_kind, "r": target_ref, "q": request_id},
    )


async def has_event(conn: AsyncConnection, action: str, target_ref: str) -> bool:
    row = await conn.execute(
        text("select 1 from vanimo.audit_events where action = :a and target_ref = :r limit 1"),
        {"a": action, "r": target_ref},
    )
    return row.first() is not None
