"""Runtime configuration.

Everything that differs between environments or regional cells is configuration,
so adding the US cell later is a config change, not a code change (D2).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal
from urllib.parse import quote
from zoneinfo import ZoneInfo

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True)
class Cell:
    """A regional deployment ("cell"). Content is stored only in its cell."""

    id: str
    aws_region: str
    data_region: Literal["IN", "US"]
    # Regions Bedrock is called from. India uses global routing in the MVP (F6).
    bedrock_region: str
    # Models a tenant in this cell may use (per-tenant allow-list, architecture §9.1).
    model_allow_list: tuple[str, ...]
    # Where "by Thursday EOD" is resolved (commitments, M5) until users can set their own.
    time_zone: str = "UTC"

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.time_zone)


CELLS: dict[str, Cell] = {
    "in": Cell(
        id="in",
        aws_region="ap-south-1",
        data_region="IN",
        bedrock_region="ap-south-1",
        model_allow_list=("anthropic.claude-haiku-5-5", "anthropic.claude-sonnet-5-5"),
        time_zone="Asia/Kolkata",
    ),
    # Added later without code changes (D2): deploy the same stacks with VANIMO_CELL=us.
    "us": Cell(
        id="us",
        aws_region="us-east-1",
        data_region="US",
        bedrock_region="us-east-1",
        model_allow_list=("anthropic.claude-haiku-5-5", "anthropic.claude-sonnet-5-5"),
        time_zone="America/New_York",
    ),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VANIMO_", env_file=".env", extra="ignore")

    env: Literal["local", "test", "dev", "prod"] = "local"
    cell: str = "in"

    # Postgres. The API connects as the non-owner `vanimo_app` role so row-level security applies.
    database_url: SecretStr = SecretStr("postgresql+psycopg://vanimo_app:vanimo_app_local@127.0.0.1:5433/vanimo")
    # In AWS the URL is assembled from parts injected by ECS (the password from Secrets Manager).
    db_host: str | None = None
    db_port: int = 5432
    db_name: str = "vanimo"
    db_app_password: SecretStr | None = None
    db_pool_size: int = 5
    # Long enough for Aurora Serverless v2 to resume from zero capacity (~15 s).
    db_connect_timeout_s: int = 30

    # Entra ID: one single-tenant app registration in the organisation's tenant (D8).
    entra_tenant_id: str = ""
    entra_client_id: str = ""
    entra_client_secret: SecretStr | None = None
    # In AWS the secret comes from Secrets Manager instead of the environment.
    entra_client_secret_arn: str | None = None
    entra_authority_host: str = "https://login.microsoftonline.com"
    api_scope_name: str = "access_as_user"

    graph_base_url: str = "https://graph.microsoft.com/v1.0"

    # Teams (M5). The web app's own origin (Teams dialogs and tabs load from it), the Teams app's
    # manifest ID (activity-feed deep links) and the bot's ID (a Developer Portal bot registration:
    # message actions need one). Empty: no Teams surface, in-app notifications only.
    web_url: str = "http://localhost:5173"
    teams_app_id: str = ""
    teams_bot_id: str = ""
    # App IDs allowed to call the bot with an Entra-issued token (the Bot Connector, once Microsoft
    # moves channels to Entra tokens; check a real request's `azp` first). Empty: Bot Framework tokens only.
    teams_bot_callers: list[str] = Field(default_factory=list)
    graph_timeout_s: float = 20.0

    # Meeting memory (M6, architecture §8.4 defaults): transcripts as L1 turns for citations, then
    # only the memory (decisions, requirements, promises...). Tier-configurable later.
    transcript_retention_days: int = Field(30, ge=1, le=365)
    memory_retention_days: int = Field(365, ge=30, le=3650)

    # Models (D7: Claude on Bedrock only). Haiku 5.5 by default (founder, 2026-10-13); Sonnet 5.5 for premium drafts.
    model_default: str = "anthropic.claude-haiku-5-5"
    model_premium: str = "anthropic.claude-sonnet-5-5"
    # Drafting (M3). "offline": the clearly labelled stand-in (no model, no AWS) until the AWS account
    # exists (founder, 2026-10-13); "bedrock": Claude on Amazon Bedrock. Prod must use Bedrock.
    drafter: Literal["offline", "bedrock"] = "offline"
    # Sonnet drafts per user per day (the rest fall back to Haiku), and a per-user rate limit
    # against runaway clients (denial of wallet, architecture §10).
    premium_drafts_per_day: int = 20
    drafts_per_minute: int = 10
    drafts_per_day: int = 300

    # Key for opaque references to identifiers (audit targets, later exclusion rules) so
    # raw IDs and addresses are never stored. Per-tenant KMS-derived keys replace this in M1.
    ref_hmac_key: SecretStr = SecretStr("local-dev-only-ref-key-change-me")
    # Master key for the M1 vault (field encryption + rule-key HMACs). KMS replaces it before
    # external customers (app/README.md, "Known deviations").
    vault_master_key: SecretStr = SecretStr("local-dev-only-vault-master-key-change-me")

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    # Email + password sign-in for local development and internal testing before the Entra app
    # exists. Never in prod (validator below). Accounts are created by an operator script.
    enable_password_auth: bool = False
    # Where workspace data comes from: "auto" = Microsoft Graph for Microsoft sign-ins, the sample
    # workspace for password sign-ins; "always" = sample workspace for everyone (demos, Entra pending).
    sample_data: Literal["auto", "always"] = "auto"
    session_ttl_s: int = 8 * 3600

    # Admin diagnostics (week-1 spikes, live health checks). Admin role is still required.
    enable_diagnostics: bool = True
    # Periodically resume interrupted purge jobs and fail scans cut off by a restart.
    background_sweeper: bool = True
    log_level: str = "INFO"

    @property
    def cell_config(self) -> Cell:
        return CELLS[self.cell]

    @property
    def entra_issuer(self) -> str:
        return f"{self.entra_authority_host}/{self.entra_tenant_id}/v2.0"

    @property
    def entra_jwks_url(self) -> str:
        return f"{self.entra_authority_host}/{self.entra_tenant_id}/discovery/v2.0/keys"

    @property
    def api_audiences(self) -> list[str]:
        # v2 access tokens carry the client ID as `aud`; accept the App ID URI form too.
        return [self.entra_client_id, f"api://{self.entra_client_id}"]

    @model_validator(mode="after")
    def _check(self) -> Settings:
        if self.db_host:
            if self.db_app_password is None:
                raise ValueError("VANIMO_DB_APP_PASSWORD is required with VANIMO_DB_HOST")
            pw = quote(self.db_app_password.get_secret_value(), safe="")
            self.database_url = SecretStr(
                f"postgresql+psycopg://vanimo_app:{pw}@{self.db_host}:{self.db_port}/{self.db_name}?sslmode=require"
            )
        if self.cell not in CELLS:
            raise ValueError(f"unknown cell {self.cell!r}; known: {sorted(CELLS)}")
        allowed = self.cell_config.model_allow_list
        for model in (self.model_default, self.model_premium):
            if model not in allowed:
                raise ValueError(f"model {model!r} is not on the {self.cell} cell allow-list")
        if self.enable_password_auth and self.env == "prod":
            raise ValueError("password sign-in is for local/dev only; disable VANIMO_ENABLE_PASSWORD_AUTH in prod")
        if self.env in ("dev", "prod"):
            missing: list[str] = []
            # A dev cell may run on password sign-in alone until the Entra app exists; prod never.
            if self.env == "prod" or not self.enable_password_auth:
                missing += [
                    name
                    for name, value in (
                        ("VANIMO_ENTRA_TENANT_ID", self.entra_tenant_id),
                        ("VANIMO_ENTRA_CLIENT_ID", self.entra_client_id),
                    )
                    if not value
                ]
                if not (self.entra_client_secret or self.entra_client_secret_arn):
                    missing.append("VANIMO_ENTRA_CLIENT_SECRET or VANIMO_ENTRA_CLIENT_SECRET_ARN")
            if self.ref_hmac_key.get_secret_value().startswith("local-dev-only"):
                missing.append("VANIMO_REF_HMAC_KEY")
            if self.vault_master_key.get_secret_value().startswith("local-dev-only"):
                missing.append("VANIMO_VAULT_MASTER_KEY")
            if self.env == "prod" and self.drafter != "bedrock":
                missing.append("VANIMO_DRAFTER=bedrock (the offline drafter is a local/dev stand-in)")
            if missing:
                raise ValueError(f"missing required settings: {', '.join(missing)}")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
