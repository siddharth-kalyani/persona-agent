"""Redaction backstops (F11, architecture §7.2 S5/S13 and §7.4): AWS services that check what our own
redaction produced, each failing closed.

* S5     `pii`        — Amazon Comprehend DetectPiiEntities inside the redactor, after our detectors.
* model  `guardrail`  — Bedrock Guardrails ApplyGuardrail on every model input and output (LlmClient).
* S13    `snapshots`/`macie` — a daily L1 snapshot per user in S3, scanned by a scheduled Macie job;
                         findings pause the tenant's pipeline (`vanimo.backstops.macie`).

Each has a clearly labelled offline stand-in for local work before the AWS account exists. One set per
process, built from settings and installed at startup (`install`); `current()` builds it from the
environment if nothing was installed, so no redactor or model call can run without its backstops.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from vanimo.backstops.guardrail import BedrockGuardrail, Guardrail, OfflineGuardrail
from vanimo.backstops.pii import ComprehendDetector, OfflinePiiDetector, PiiDetector

if TYPE_CHECKING:
    from vanimo.config import Settings

MACIE_OFFLINE_LABEL = "Offline stand-in for Amazon Macie: the same L1 snapshot, scanned by Vanimo's own detectors"
MACIE_LABEL = "Amazon Macie (daily job over the L1 snapshot bucket)"


@dataclass
class Backstops:
    pii: PiiDetector
    guardrail: Guardrail
    comprehend_scope: Literal["all", "flagged"] = "all"
    macie_mode: Literal["offline", "aws"] = "offline"
    # S3 client and Macie reader for "aws"; None offline (built lazily, see `vanimo.backstops.snapshots`).
    snapshot_store: Any = None
    macie_reader: Any = None
    snapshot_every_hours: int = 24

    @property
    def macie_label(self) -> str:
        return MACIE_LABEL if self.macie_mode == "aws" else MACIE_OFFLINE_LABEL


def build(settings: Settings) -> Backstops:
    region = settings.cell_config.aws_region
    pii: PiiDetector = ComprehendDetector(region) if settings.pii_detector == "comprehend" else OfflinePiiDetector()
    guardrail: Guardrail = (
        BedrockGuardrail(settings.guardrail_id, settings.guardrail_version, region)
        if settings.guardrail == "bedrock"
        else OfflineGuardrail()
    )
    store = reader = None
    if settings.macie == "aws":
        from vanimo.backstops.macie import MacieReader
        from vanimo.backstops.snapshots import S3SnapshotStore

        store = S3SnapshotStore(settings.l1_snapshot_bucket, region)
        reader = MacieReader(settings.l1_snapshot_bucket, region)
    return Backstops(
        pii=pii,
        guardrail=guardrail,
        comprehend_scope=settings.comprehend_scope,
        macie_mode=settings.macie,
        snapshot_store=store,
        macie_reader=reader,
        snapshot_every_hours=settings.snapshot_every_hours,
    )


_current: Backstops | None = None


def install(backstops: Backstops | None) -> Backstops | None:
    """Make `backstops` the process's set; returns the previous one (to restore at shutdown)."""
    global _current
    previous, _current = _current, backstops
    return previous


def current() -> Backstops:
    global _current
    if _current is None:
        from vanimo.config import get_settings

        _current = build(get_settings())
    return _current
