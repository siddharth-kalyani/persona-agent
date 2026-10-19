"""Process-wide services, created once at startup and shared by requests."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from vanimo.auth.entra import JwksCache, TokenValidator
from vanimo.auth.local import LoginThrottle
from vanimo.auth.obo import OboClient
from vanimo.backstops import Backstops
from vanimo.backstops import build as build_backstops
from vanimo.backstops.guardrail import GuardrailBlocked
from vanimo.config import Settings
from vanimo.db.session import make_engine
from vanimo.drafting.context import DirectoryCache, DraftThrottle
from vanimo.llm.router import LlmClient, ModelRouter
from vanimo.vault import Vault


@dataclass
class AppState:
    settings: Settings
    engine: AsyncEngine
    http: httpx.AsyncClient
    validator: TokenValidator
    router: ModelRouter
    obo: OboClient | None = None
    login_throttle: LoginThrottle = field(default_factory=LoginThrottle)
    draft_throttle: DraftThrottle = field(default_factory=DraftThrottle)
    directory_cache: DirectoryCache = field(default_factory=DirectoryCache)
    _vault: Vault | None = field(default=None, repr=False)
    # Background work started by requests (scans, purge jobs); kept referenced until done.
    tasks: set[asyncio.Task[Any]] = field(default_factory=set, repr=False)

    def spawn(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    _llm: LlmClient | None = field(default=None, repr=False)
    _backstops: Backstops | None = field(default=None, repr=False)

    @property
    def backstops(self) -> Backstops:
        """Comprehend, Guardrails and Macie (or their offline stand-ins), from settings (F11)."""
        if self._backstops is None:
            self._backstops = build_backstops(self.settings)
        return self._backstops

    @property
    def llm(self) -> LlmClient:
        # Created on first use so local runs without AWS credentials still start.
        if self._llm is None:
            self._llm = LlmClient(
                self.settings, self.router, self.backstops.guardrail, on_block=self._guardrail_blocked
            )
        return self._llm

    async def _guardrail_blocked(self, blocked: GuardrailBlocked) -> None:
        from vanimo.backstops import events

        stage = "model_input" if blocked.source == "INPUT" else "model_output"
        await events.record(self.engine, source="guardrail", stage=stage, outcome="blocked", kinds=blocked.kinds)

    @property
    def vault(self) -> Vault:
        if self._vault is None:
            self._vault = Vault(self.settings.vault_master_key.get_secret_value())
        return self._vault

    async def aclose(self) -> None:
        for task in list(self.tasks):
            task.cancel()
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
