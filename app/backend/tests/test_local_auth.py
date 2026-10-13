"""Local email + password sign-in (local/dev only)."""

from __future__ import annotations

import uuid

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from vanimo.auth import passwords
from vanimo.config import Settings
from vanimo.ops.local_user import upsert_local_user
from vanimo.state import AppState

pytestmark = pytest.mark.db
NEW_PASSWORD = "correct horse battery staple"


@pytest.fixture
def account(database: dict[str, str], settings: Settings) -> tuple[str, str]:
    email = f"Founder.{uuid.uuid4().hex[:6]}@Example.COM"
    one_time = upsert_local_user(database["owner"], email, "superadmin", reset=False, settings=settings)
    return email, one_time


async def _login(client: httpx.AsyncClient, email: str, password: str) -> httpx.Response:
    return await client.post("/api/auth/login", json={"email": email, "password": password})


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_password_hashing_and_rules() -> None:
    h = passwords.hash_password("s3cret-enough-pass")
    assert h.startswith("scrypt$32768$8$1$") and "s3cret" not in h
    assert passwords.verify_password("s3cret-enough-pass", h)
    assert not passwords.verify_password("wrong", h)
    assert not passwords.verify_password("x", "not-a-hash")
    otp = passwords.new_one_time_password()
    assert len(otp) == 19 and otp.count("-") == 3
    cases = [
        ("short", "password_too_short"),
        ("password1234", "password_too_common"),
        ("aaaaaaaaaaaaaaa", "password_too_common"),
        ("my-founder-name-1", "password_contains_email"),
    ]
    for bad, code in cases:
        with pytest.raises(passwords.WeakPassword) as exc:
            passwords.check_new_password(bad, email="founder@example.com")
        assert exc.value.code == code
    with pytest.raises(passwords.WeakPassword, match="unchanged"):
        passwords.check_new_password(NEW_PASSWORD, email="a@b.c", current=NEW_PASSWORD)
    t = passwords.new_session_token()
    assert t.startswith("vnm_s_") and len(passwords.token_hash(t)) == 64


def test_password_auth_never_in_prod() -> None:
    with pytest.raises(ValidationError, match="local/dev only"):
        Settings(env="prod", enable_password_auth=True)
    # A dev cell may run on password sign-in alone before the Entra app exists.
    assert Settings(env="dev", enable_password_auth=True, ref_hmac_key="k" * 32).enable_password_auth


async def test_auth_config(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/auth/config")).json() == {"passwordSignIn": True, "microsoftSignIn": True}


async def test_first_sign_in_forces_password_change(client: httpx.AsyncClient, account: tuple[str, str]) -> None:
    email, one_time = account
    resp = await _login(client, email.upper(), one_time)  # emails are case-insensitive
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mustChangePassword"] is True
    assert body["roles"] == ["Vanimo.Admin", "Vanimo.SuperAdmin", "Vanimo.User"]
    token = body["token"]

    # Everything except changing the password is blocked until the password is changed.
    blocked = await client.get("/api/me", headers=_bearer(token))
    assert blocked.status_code == 403 and blocked.json() == {"error": "password_change_required"}
    info = await client.get("/api/auth/session", headers=_bearer(token))
    assert info.json()["mustChangePassword"] is True and info.json()["method"] == "password"

    weak = await client.post(
        "/api/auth/change-password", headers=_bearer(token), json={"currentPassword": one_time, "newPassword": "short"}
    )
    assert weak.status_code == 422 and weak.json() == {"error": "password_too_short"}
    wrong = await client.post(
        "/api/auth/change-password",
        headers=_bearer(token),
        json={"currentPassword": "nope", "newPassword": NEW_PASSWORD},
    )
    assert wrong.status_code == 401

    changed = await client.post(
        "/api/auth/change-password",
        headers=_bearer(token),
        json={"currentPassword": one_time, "newPassword": NEW_PASSWORD},
    )
    assert changed.status_code == 200 and changed.json()["mustChangePassword"] is False
    new_token = changed.json()["token"]

    # The old session and the one-time password no longer work.
    assert (await client.get("/api/auth/session", headers=_bearer(token))).status_code == 401
    assert (await _login(client, email, one_time)).status_code == 401

    me = await client.get("/api/me", headers=_bearer(new_token))
    assert me.status_code == 200, me.text
    assert me.json()["signInMethod"] == "password" and me.json()["microsoft365Connected"] is False
    assert me.json()["recentSent"] == [] and me.json()["onboardingState"] == "review_pending"

    # Super-admin implies admin, but Microsoft 365 checks need a Microsoft sign-in.
    diag = await client.post("/api/admin/diagnostics/run", headers=_bearer(new_token))
    assert diag.status_code == 409 and diag.json() == {"error": "microsoft_signin_required"}

    assert (await client.post("/api/auth/logout", headers=_bearer(new_token))).status_code == 204
    assert (await client.get("/api/me", headers=_bearer(new_token))).status_code == 401


async def test_wrong_and_unknown_logins_look_the_same(client: httpx.AsyncClient, account: tuple[str, str]) -> None:
    email, _ = account
    a = await _login(client, email, "wrong-password")
    b = await _login(client, "nobody@example.com", "wrong-password")
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json() == {"error": "invalid_credentials"}


async def test_lockout_after_five_failures(client: httpx.AsyncClient, account: tuple[str, str]) -> None:
    email, one_time = account
    for _ in range(5):
        assert (await _login(client, email, "wrong-password")).status_code == 401
    # Even the right password fails while locked, with the same answer as a wrong one (no enumeration).
    locked = await _login(client, email, one_time)
    assert locked.status_code == 401 and locked.json() == {"error": "invalid_credentials"}


async def test_login_throttle_per_address(client: httpx.AsyncClient) -> None:
    codes = [(await _login(client, f"x{i}@example.com", "pw")).status_code for i in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429


async def test_disabled_password_auth(client: httpx.AsyncClient, app_state: AppState, account: tuple[str, str]) -> None:
    email, one_time = account
    token = (await _login(client, email, one_time)).json()["token"]
    app_state.settings = app_state.settings.model_copy(update={"enable_password_auth": False})
    assert (await _login(client, email, one_time)).status_code == 404
    resp = await client.get("/api/auth/session", headers=_bearer(token))
    assert resp.status_code == 401 and resp.json() == {"error": "password_signin_disabled"}


async def test_forged_session_token_rejected(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/me", headers=_bearer("vnm_s_" + "A" * 43))
    assert resp.status_code == 401 and resp.json() == {"error": "session_expired"}


async def test_api_role_cannot_read_credentials_or_sessions(database: dict[str, str], account: tuple[str, str]) -> None:
    engine = create_async_engine(database["app"])
    async with engine.connect() as conn:
        for table in ("local_credentials", "sessions"):
            with pytest.raises(DBAPIError, match="permission denied"):
                await conn.execute(text(f"select * from vanimo.{table}"))  # noqa: S608
            await conn.rollback()
    await engine.dispose()


def test_reset_issues_new_one_time_password(
    database: dict[str, str], settings: Settings, account: tuple[str, str]
) -> None:
    email, first = account
    with pytest.raises(SystemExit, match="already exists"):
        upsert_local_user(database["owner"], email, "user", reset=False, settings=settings)
    second = upsert_local_user(database["owner"], email, "superadmin", reset=True, settings=settings)
    assert second != first


async def test_parallel_guesses_cannot_exceed_the_lockout(
    client: httpx.AsyncClient, app_state: AppState, account: tuple[str, str]
) -> None:
    import asyncio

    from vanimo.auth.local import LoginThrottle

    email, one_time = account
    app_state.login_throttle = LoginThrottle(limit=1000)  # isolate the database lockout
    await asyncio.gather(*(_login(client, email, f"guess-{i}") for i in range(12)))
    assert (await _login(client, email, one_time)).status_code == 401  # locked after 5, not 12


async def test_expired_lock_starts_a_fresh_window(
    client: httpx.AsyncClient, database: dict[str, str], account: tuple[str, str]
) -> None:
    import psycopg

    email, one_time = account
    for _ in range(5):
        await _login(client, email, "wrong-password")
    with psycopg.connect(database["owner"].replace("postgresql+psycopg://", "postgresql://")) as conn:
        conn.execute(
            "update vanimo.local_credentials set locked_until = now() - interval '1 second' where email = %s",
            (email.lower(),),
        )
    # One more wrong attempt after expiry must not re-lock immediately.
    assert (await _login(client, email, "wrong-password")).status_code == 401
    assert (await _login(client, email, one_time)).status_code == 200


async def test_non_ascii_passwords(client: httpx.AsyncClient, account: tuple[str, str]) -> None:
    email, one_time = account
    token = (await _login(client, email, one_time)).json()["token"]
    phrase = "café crème brûlée ☕ 2026"
    resp = await client.post(
        "/api/auth/change-password", headers=_bearer(token), json={"currentPassword": one_time, "newPassword": phrase}
    )
    assert resp.status_code == 200, resp.text
    # NFKC: a decomposed "é" (e + combining accent) is the same password.
    decomposed = phrase.replace("é", "é")
    assert (await _login(client, email, decomposed)).status_code == 200


async def test_password_change_gate_covers_admin_routes(client: httpx.AsyncClient, account: tuple[str, str]) -> None:
    email, one_time = account
    token = (await _login(client, email, one_time)).json()["token"]
    for method, path in [
        ("POST", "/api/admin/diagnostics/run"),
        ("POST", "/api/admin/diagnostics/draft-probe"),
        ("GET", "/api/me"),
        ("POST", "/api/auth/change-password/"),
    ]:
        resp = await client.request(method, path, headers=_bearer(token))
        assert resp.status_code in (403, 307), (path, resp.status_code)
        if resp.status_code == 403:
            assert resp.json() == {"error": "password_change_required"}


async def test_sessions_need_a_fresh_login_nonce(database: dict[str, str], account: tuple[str, str]) -> None:
    """The API role can't mint a session for a user without a successful password check."""
    from sqlalchemy.exc import DBAPIError

    email, _ = account
    engine = create_async_engine(database["app"])
    async with engine.connect() as conn:
        user_id = (
            await conn.execute(text("select user_id from vanimo_private.password_login_begin(:e)"), {"e": email})
        ).scalar_one()
        await conn.commit()
        with pytest.raises(DBAPIError, match="cannot create session"):
            await conn.execute(
                text("select vanimo_private.session_create(:u, :n, :h, 60)"),
                {"u": user_id, "n": "0" * 64, "h": "1" * 64},
            )
    await engine.dispose()


async def test_session_ttl_is_capped(client: httpx.AsyncClient, app_state: AppState, account: tuple[str, str]) -> None:
    from datetime import UTC, datetime, timedelta

    email, one_time = account
    app_state.settings = app_state.settings.model_copy(update={"session_ttl_s": 10 * 24 * 3600})
    body = (await _login(client, email, one_time)).json()
    expires = datetime.fromisoformat(body["expiresAt"])
    assert expires - datetime.now(UTC) <= timedelta(hours=12, minutes=1)


def test_reset_keeps_roles_unless_given(database: dict[str, str], settings: Settings, account: tuple[str, str]) -> None:
    import psycopg

    email, _ = account
    upsert_local_user(database["owner"], email, None, reset=True, settings=settings)
    with psycopg.connect(database["owner"].replace("postgresql+psycopg://", "postgresql://")) as conn:
        roles = conn.execute("select roles from vanimo.local_credentials where email = %s", (email.lower(),)).fetchone()
    assert roles == (["Vanimo.User", "Vanimo.Admin", "Vanimo.SuperAdmin"],)


async def test_failed_logins_are_audited(
    client: httpx.AsyncClient, database: dict[str, str], account: tuple[str, str]
) -> None:
    import psycopg

    email, _ = account
    for _ in range(5):
        await _login(client, email, "wrong-password")
    with psycopg.connect(database["owner"].replace("postgresql+psycopg://", "postgresql://")) as conn:
        actions = [
            r[0]
            for r in conn.execute(
                "select a.action from vanimo.audit_events a join vanimo.local_credentials c on c.user_id = a.user_id "
                "where c.email = %s order by a.id",
                (email.lower(),),
            )
        ]
    assert actions == ["auth.password_login_failed"] * 4 + ["auth.account_locked"]
