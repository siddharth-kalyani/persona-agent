from __future__ import annotations

import pytest
from pydantic import ValidationError

from vanimo.config import Settings
from vanimo.llm.router import ModelNotAllowed, ModelRouter


def test_defaults_route_haiku_then_sonnet() -> None:
    router = ModelRouter(Settings(env="test"))
    assert router.model_for("default") == "anthropic.claude-haiku-5-5"
    assert router.model_for("premium") == "anthropic.claude-sonnet-5-5"


def test_router_enforces_allow_list() -> None:
    with pytest.raises(ModelNotAllowed):
        ModelRouter(Settings(env="test")).check("anthropic.claude-fable-5-1")


def test_settings_reject_models_off_the_allow_list() -> None:
    with pytest.raises(ValidationError, match="allow-list"):
        Settings(env="test", model_premium="anthropic.claude-fable-5-1")


def test_unknown_cell_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown cell"):
        Settings(env="test", cell="eu")


def test_cells_are_config() -> None:
    assert Settings(env="test", cell="in").cell_config.aws_region == "ap-south-1"
    assert Settings(env="test", cell="us").cell_config.aws_region == "us-east-1"


def test_deployed_envs_require_entra_and_keys() -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(env="prod")
    msg = str(exc.value)
    assert "VANIMO_ENTRA_TENANT_ID" in msg and "VANIMO_REF_HMAC_KEY" in msg and "VANIMO_DRAFTER" in msg
    ok = Settings(
        env="prod",
        drafter="bedrock",
        entra_tenant_id="t",
        entra_client_id="c",
        entra_client_secret_arn="arn:aws:secretsmanager:x",
        ref_hmac_key="k" * 32,
        vault_master_key="v" * 32,
    )
    assert ok.entra_issuer.endswith("/t/v2.0")
