"""Process-wide services, created once at startup and shared by requests."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from vanimo.auth.entra import JwksCache, TokenValidator
from vanimo.auth.obo import OboClient
from vanimo.config import Settings
from vanimo.db.session import make_engine
from vanimo.llm.router import LlmClient, ModelRouter


@dataclass
class AppState:
    settings: Settings
    engine: AsyncEngine
    http: httpx.AsyncClient
    validator: TokenValidator
    router: ModelRouter
    obo: OboClient | None = None
    _llm: LlmClient | None = field(default=None, repr=False)

    @property
    def llm(self) -> LlmClient:
        # Created on first use so local runs without AWS credentials still start.
        if self._llm is None:
            self._llm = LlmClient(self.settings, self.router)
        return self._llm

    async def aclose(self) -> None:
        await self.http.aclose()
        await self.engine.dispose()


def resolve_client_secret(settings: Settings) -> str | None:
    if settings.entra_client_secret is not None:
        return settings.entra_client_secret.get_secret_value()
    if settings.entra_client_secret_arn:
        import boto3

        sm = boto3.client("secretsmanager", region_name=settings.cell_config.aws_region)
        return sm.get_secret_value(SecretId=settings.entra_client_secret_arn)["SecretString"]
    return None


def build_state(settings: Settings, *, http: httpx.AsyncClient | None = None) -> AppState:
    http = http or httpx.AsyncClient(timeout=settings.graph_timeout_s, follow_redirects=False)
    secret = resolve_client_secret(settings)
    return AppState(
        settings=settings,
        engine=make_engine(settings),
        http=http,
        validator=TokenValidator(settings, JwksCache(settings.entra_jwks_url, http)),
        router=ModelRouter(settings),
        obo=OboClient(settings, secret) if secret and settings.entra_client_id else None,
    )
