"""The hand-setup files (F13) match what the CDK stacks would create."""

from __future__ import annotations

import json

from vanimo_infra import manual
from vanimo_infra.backstops_stack import GUARDRAIL_PII_TYPES, INDIA_PATTERNS


def test_committed_files_are_current() -> None:
    expected = manual.files()
    on_disk = {p.name for p in manual.OUT.glob("*.json")}
    assert on_disk == set(expected), "run: uv run python -m vanimo_infra.manual"
    for name, doc in expected.items():
        assert (manual.OUT / name).read_bytes().decode("utf-8") == manual.render(doc), (
            f"{name} is stale; run: uv run python -m vanimo_infra.manual"
        )


def test_guardrail_blocks_every_type_and_indian_identifier() -> None:
    config = manual.guardrail()["sensitiveInformationPolicyConfig"]
    assert {e["type"] for e in config["piiEntitiesConfig"]} == set(GUARDRAIL_PII_TYPES)
    assert {e["action"] for e in config["piiEntitiesConfig"]} == {"BLOCK"}
    assert {r["name"]: r["pattern"] for r in config["regexesConfig"]} == {n: p for n, (p, _) in INDIA_PATTERNS.items()}


def test_app_policy_is_least_privilege() -> None:
    statements = manual.app_policy()["Statement"]
    actions = sorted(a for s in statements for a in ([s["Action"]] if isinstance(s["Action"], str) else s["Action"]))
    assert actions == sorted([
        "bedrock-mantle:CreateInference", "comprehend:DetectPiiEntities", "bedrock:ApplyGuardrail",
        "s3:PutObject", "s3:DeleteObject", "macie2:ListFindings", "macie2:GetFindings",
    ])  # fmt: skip
    assert not any("Get" in a and a.startswith("s3:") for a in actions)  # the app never reads snapshots
    snapshot = next(s for s in statements if s["Sid"] == "SnapshotWrites")
    assert snapshot["Resource"].endswith("/l1/*")


def test_only_macie_reads_the_bucket() -> None:
    policy = json.dumps(manual.bucket_policy())
    assert "AWSServiceRoleForAmazonMacie" in policy and '"aws:SecureTransport": "false"' in policy
