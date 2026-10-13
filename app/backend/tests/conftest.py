"""Shared fixtures: a migrated test database, signed test tokens, a mocked Graph."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import time
import uuid
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import httpx
import jwt
import psycopg
import pytest
import respx
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import rsa

from vanimo.auth.entra import JwksCache, Principal, TokenValidator
from vanimo.config import Settings
from vanimo.db.session import make_engine
from vanimo.llm.router import ModelRouter
from vanimo.ops.bootstrap_db import bootstrap
from vanimo.state import AppState

# Tests never read a developer's app/backend/.env (it may enable features the tests assert on).
Settings.model_config["env_file"] = None

BACKEND = Path(__file__).resolve().parents[1]
TENANT = "11111111-1111-1111-1111-111111111111"
CLIENT_ID = "22222222-2222-2222-2222-222222222222"
OTHER_TENANT = "99999999-9999-9999-9999-999999999999"
KID = "test-key-1"

ADMIN_URL = os.environ.get("VANIMO_TEST_ADMIN_URL", "postgresql://postgres:postgres_local@127.0.0.1:5433/postgres")
TEST_DB = "vanimo_test"
# Roles are cluster-wide, so the test database shares them with the local dev database: use the
# same local passwords, or running the tests would lock the dev server out.
OWNER_PW = os.environ.get("VANIMO_DB_OWNER_PASSWORD", "vanimo_owner_local")
APP_PW = os.environ.get("VANIMO_DB_APP_PASSWORD", "vanimo_app_local")


def pytest_asyncio_loop_factories(
    config: pytest.Config, item: pytest.Item
) -> dict[str, Callable[[], asyncio.AbstractEventLoop]]:
    # psycopg's async mode can't run on Windows' default Proactor loop (Linux/CI unaffected).
    if sys.platform == "win32":
        return {"selector": asyncio.SelectorEventLoop}
    return {"default": asyncio.new_event_loop}


def _db_host_part() -> str:
    return ADMIN_URL.split("@", 1)[1].rsplit("/", 1)[0]


@pytest.fixture(scope="session")
def database() -> dict[str, str]:
    try:
        with psycopg.connect(ADMIN_URL, autocommit=True, connect_timeout=3) as conn:
            conn.execute(f'drop database if exists "{TEST_DB}" with (force)')
    except psycopg.OperationalError:
        pytest.skip("local Postgres not running (docker compose -f app/docker-compose.yml up -d)")
    bootstrap(ADMIN_URL, TEST_DB, OWNER_PW, APP_PW)
    host = _db_host_part()
    owner_url = f"postgresql+psycopg://vanimo_owner:{OWNER_PW}@{host}/{TEST_DB}"
    app_url = f"postgresql+psycopg://vanimo_app:{APP_PW}@{host}/{TEST_DB}"
    os.environ["VANIMO_DB_OWNER_URL"] = owner_url
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    return {"owner": owner_url, "app": app_url}


@pytest.fixture(scope="session")
def rsa_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _b64(n: int) -> str:
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@pytest.fixture(scope="session")
def jwks(rsa_key: rsa.RSAPrivateKey) -> dict:
    pub = rsa_key.public_key().public_numbers()
    return {"keys": [{"kty": "RSA", "use": "sig", "kid": KID, "n": _b64(pub.n), "e": _b64(pub.e)}]}


@pytest.fixture
def settings(database: dict[str, str]) -> Settings:
    return Settings(
        env="test",
        database_url=database["app"],
        entra_tenant_id=TENANT,
        entra_client_id=CLIENT_ID,
        cors_origins=[],
        enable_password_auth=True,
    )


@pytest.fixture
def unit_settings() -> Settings:
    """Settings for tests that don't touch the database."""
    return Settings(env="test", entra_tenant_id=TENANT, entra_client_id=CLIENT_ID, cors_origins=[])


TokenFactory = Callable[..., str]


@pytest.fixture
def make_token(rsa_key: rsa.RSAPrivateKey) -> TokenFactory:
    def _make(
        *,
        oid: str | None = None,
        tid: str = TENANT,
        aud: str = CLIENT_ID,
        roles: tuple[str, ...] = ("Vanimo.User",),
        scp: str = "access_as_user",
        exp_in: int = 3600,
        kid: str = KID,
        extra: dict | None = None,
    ) -> str:
        now = int(time.time())
        claims = {
            "iss": f"https://login.microsoftonline.com/{tid}/v2.0",
            "aud": aud,
            "tid": tid,
            "oid": oid or str(uuid.uuid4()),
            "iat": now - 10,
            "nbf": now - 10,
            "exp": now + exp_in,
            "ver": "2.0",
            "azp": CLIENT_ID,
            "scp": scp,
            "roles": list(roles),
            **(extra or {}),
        }
        return jwt.encode(claims, rsa_key, algorithm="RS256", headers={"kid": kid})

    return _make


class FakeObo:
    """Stands in for MSAL's On-Behalf-Of call."""

    async def graph_token(self, principal: Principal) -> str:
        return "graph-token-for-" + principal.entra_oid


@pytest.fixture
def graph_mock(jwks: dict) -> respx.MockRouter:
    with respx.mock(assert_all_called=False) as router:
        router.get(f"https://login.microsoftonline.com/{TENANT}/discovery/v2.0/keys").mock(
            return_value=httpx.Response(200, json=jwks)
        )
        yield router


@pytest.fixture
async def app_state(settings: Settings, graph_mock: respx.MockRouter) -> AsyncIterator[AppState]:
    http = httpx.AsyncClient()
    state = AppState(
        settings=settings,
        engine=make_engine(settings),
        http=http,
        validator=TokenValidator(settings, JwksCache(settings.entra_jwks_url, http)),
        router=ModelRouter(settings),
        obo=FakeObo(),  # type: ignore[arg-type]
    )
    yield state
    await state.aclose()


@pytest.fixture
async def client(settings: Settings, app_state: AppState) -> AsyncIterator[httpx.AsyncClient]:
    from vanimo.main import create_app

    app = create_app(settings, app_state)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


def log_lines(text: str) -> list[dict]:
    return [json.loads(line) for line in text.splitlines() if line.startswith("{")]
