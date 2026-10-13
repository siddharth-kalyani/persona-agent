"""Local email + password sign-in: sessions and credentials, through the SECURITY DEFINER
functions of migration 0002 (the API role can't touch the tables directly)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime

import anyio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from vanimo.auth.entra import KNOWN_ROLES, AuthError, Principal
from vanimo.auth.passwords import DUMMY_HASH, token_hash, verify_password
from vanimo.db.session import UserRef


@dataclass(frozen=True)
class LoginRow:
    user_id: object
    tenant_id: object
    password_hash: str
    must_change: bool
    locked_until: datetime | None
    roles: list[str]


async def check_credentials(engine: AsyncEngine, email: str, password: str) -> LoginRow:
    """Verify a password. Same work and same error whether or not the email exists."""
    async with engine.begin() as conn:
        row = (
            await conn.execute(text("select * from vanimo_private.password_login_lookup(:e)"), {"e": email.lower()})
        ).first()
    stored = row.password_hash if row else DUMMY_HASH
    ok = await anyio.to_thread.run_sync(verify_password, password, stored)
    if row is None:
        raise AuthError("invalid_credentials")
    login = LoginRow(row.user_id, row.tenant_id, row.password_hash, row.must_change, row.locked_until, list(row.roles))
    if login.locked_until and login.locked_until > datetime.now(UTC):
        raise AuthError("account_locked", 423)
    async with engine.begin() as conn:
        await conn.execute(text("select vanimo_private.password_login_result(:u, :ok)"), {"u": login.user_id, "ok": ok})
    if not ok:
        raise AuthError("invalid_credentials")
    return login


async def create_session(engine: AsyncEngine, user_id: object, token: str, ttl_s: int) -> datetime:
    async with engine.begin() as conn:
        return (
            await conn.execute(
                text("select vanimo_private.session_create(:u, :h, :ttl)"),
                {"u": user_id, "h": token_hash(token), "ttl": ttl_s},
            )
        ).scalar_one()


async def resolve_session(engine: AsyncEngine, token: str) -> Principal:
    async with engine.begin() as conn:
        row = (
            await conn.execute(text("select * from vanimo_private.session_resolve(:h)"), {"h": token_hash(token)})
        ).first()
    if row is None:
        raise AuthError("session_expired")
    roles = frozenset(r for r in row.roles if r in KNOWN_ROLES)
    if not roles:
        raise AuthError("not_assigned", 403)
    return Principal(
        entra_tenant_id="",
        entra_oid="",
        roles=roles,
        scopes=frozenset(),
        access_token="",
        auth_method="password",
        local_user=UserRef(tenant_id=row.tenant_id, user_id=row.user_id),
        email=row.email,
        must_change_password=row.must_change,
    )


async def revoke_session(engine: AsyncEngine, token: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("select vanimo_private.session_revoke(:h)"), {"h": token_hash(token)})


async def change_password(engine: AsyncEngine, token: str, new_hash: str) -> object:
    async with engine.begin() as conn:
        return (
            await conn.execute(
                text("select vanimo_private.password_change(:h, :p)"), {"h": token_hash(token), "p": new_hash}
            )
        ).scalar_one()


class LoginThrottle:
    """In-process sliding window per client address (one API task in the MVP). Account lockout
    in the database is the durable control; this just blunts password spraying."""

    def __init__(self, limit: int = 10, window_s: float = 60.0) -> None:
        self._limit = limit
        self._window = window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self._window:
            hits.popleft()
        if len(hits) >= self._limit:
            raise AuthError("too_many_attempts", 429)
        hits.append(now)
        if len(self._hits) > 10_000:  # bound memory under a spray from many addresses
            self._hits.clear()
