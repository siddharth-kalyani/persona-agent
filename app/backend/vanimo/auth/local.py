"""Local email + password sign-in: sessions and credentials, through the SECURITY DEFINER
functions of migrations 0002-0003 (the API role can't touch the tables directly)."""

from __future__ import annotations

import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime

import anyio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from vanimo.auth.entra import KNOWN_ROLES, AuthError, Principal
from vanimo.auth.passwords import DUMMY_HASH, token_hash, verify_password
from vanimo.db.session import UserRef


@dataclass(frozen=True)
class LoginResult:
    user: UserRef
    must_change: bool
    roles: list[str]
    # Single-use proof of this successful check; session_create consumes it (migration 0003).
    nonce: str


class LoginFailed(AuthError):
    """Wrong password, unknown email or locked account — deliberately indistinguishable."""

    def __init__(self, user: UserRef | None = None, *, locked: bool = False) -> None:
        super().__init__("invalid_credentials")
        self.user = user  # set when the email exists, for the audit log only
        self.locked = locked


# scrypt needs 32 MiB per call; cap concurrent hashes so a burst of logins can't exhaust memory.
_SCRYPT_SLOTS = anyio.Semaphore(2)


async def run_scrypt(fn, *args):  # type: ignore[no-untyped-def]
    async with _SCRYPT_SLOTS:
        return await anyio.to_thread.run_sync(fn, *args)


async def check_credentials(engine: AsyncEngine, email: str, password: str) -> LoginResult:
    """Verify a password. Same work, same error and same number of database round trips whether
    the email is unknown, the password is wrong or the account is locked."""
    async with engine.begin() as conn:
        row = (
            await conn.execute(text("select * from vanimo_private.password_login_begin(:e)"), {"e": email.lower()})
        ).first()
    usable = row is not None and not row.locked
    ok = await run_scrypt(verify_password, password, row.password_hash if usable else DUMMY_HASH)
    if row is None:
        raise LoginFailed()
    user = UserRef(tenant_id=row.tenant_id, user_id=row.user_id)
    if not usable or not ok:
        raise LoginFailed(user, locked=bool(row.locked or row.now_locked))
    nonce = secrets.token_urlsafe(32)
    async with engine.begin() as conn:
        await conn.execute(
            text("select vanimo_private.password_login_succeeded(:u, :n)"), {"u": row.user_id, "n": token_hash(nonce)}
        )
    return LoginResult(user=user, must_change=row.must_change, roles=list(row.roles), nonce=nonce)


async def create_session(engine: AsyncEngine, login: LoginResult, token: str, ttl_s: int) -> datetime:
    async with engine.begin() as conn:
        return (
            await conn.execute(
                text("select vanimo_private.session_create(:u, :n, :h, :ttl)"),
                {"u": login.user.user_id, "n": token_hash(login.nonce), "h": token_hash(token), "ttl": ttl_s},
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
        if len(self._hits) > 10_000:  # bound memory: evict the oldest keys, never reset everyone
            for stale in list(self._hits)[:1000]:
                del self._hits[stale]
