"""Model input/output backstop (architecture §7.4, F11): Amazon Bedrock Guardrails `ApplyGuardrail`.

Every model call checks its input (after L1) and its output (before anyone re-hydrates or shows it).
A finding blocks the call. The guardrail's sensitive-information filter covers names, addresses,
contact details and US/UK/CA identifiers; custom regexes in the guardrail (`app/infra`) add the Indian
ones it lacks (Aadhaar, PAN, GSTIN, IFSC, UPI, voter ID).

Vanimo's own marks (⟦PERSON_…⟧ tokens, [PAN] slots, never-send placeholders) are replaced by a
neutral word before the check, so a token is never mistaken for a value.

**ApplyGuardrail responses carry the raw matched text** (`match`). Only entity type names and
counts are taken from a response; it is never logged or stored.

* `BedrockGuardrail` — the real check. Any error raises `GuardrailUnavailable`: the model is not
  called (or its output not used).
* `OfflineGuardrail` — the clearly labelled stand-in: our own Tier R / Tier P detectors run on the
  same text.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Sequence
from typing import Any, Literal, Protocol

from vanimo.logs import get_logger
from vanimo.redaction import detectors
from vanimo.redaction.marks import L1_MARKS

log = get_logger("vanimo.backstops")

Source = Literal["INPUT", "OUTPUT"]
# One ApplyGuardrail request takes up to 1,000 text units of 1,000 characters; stay well under.
MAX_REQUEST_CHARS = 400_000
NEUTRAL = "someone"
OTHER_POLICIES = (
    "topicPolicy",
    "contentPolicy",
    "wordPolicy",
    "contextualGroundingPolicy",
    "automatedReasoningPolicy",
)


class GuardrailBlocked(Exception):
    """The guardrail found sensitive data. `kinds`: entity type → count (content-free)."""

    def __init__(self, source: Source, kinds: dict[str, int]) -> None:
        super().__init__(f"guardrail_blocked_{source.lower()}")
        self.source = source
        self.kinds = kinds


class GuardrailUnavailable(Exception):
    """The guardrail couldn't be reached: fail closed. Content-free."""


class Guardrail(Protocol):
    name: Literal["bedrock", "offline"]
    label: str

    async def check(self, source: Source, texts: Sequence[str]) -> None:
        """Returns if clean; raises GuardrailBlocked or GuardrailUnavailable."""
        ...


def neutral(text: str) -> str:
    """L1 marks replaced by a plain word: free text is what the guardrail must judge."""
    return L1_MARKS.sub(NEUTRAL, text)


def _batches(texts: Sequence[str]) -> list[list[str]]:
    out: list[list[str]] = [[]]
    size = 0
    for t in texts:
        for i in range(0, len(t), MAX_REQUEST_CHARS):
            piece = t[i : i + MAX_REQUEST_CHARS]
            if size + len(piece) > MAX_REQUEST_CHARS and out[-1]:
                out.append([])
                size = 0
            out[-1].append(piece)
            size += len(piece)
    return [b for b in out if b]


def kinds_of(response: dict[str, Any]) -> dict[str, int]:
    """Entity types and regex names the guardrail acted on. Never reads `match`."""
    found: Counter[str] = Counter()
    for a in response.get("assessments") or []:
        policy = a.get("sensitiveInformationPolicy") or {}
        for e in policy.get("piiEntities") or []:
            if e.get("action") in ("BLOCKED", "ANONYMIZED"):
                found[str(e.get("type", "UNKNOWN"))[:60]] += 1
        for r in policy.get("regexes") or []:
            if r.get("action") in ("BLOCKED", "ANONYMIZED"):
                found[str(r.get("name", "regex"))[:60]] += 1
        # Any other policy (none configured today) still blocks, by name only. Metrics and details
        # that ride along in an assessment aren't policies.
        for other in OTHER_POLICIES:
            if a.get(other):
                found[f"policy:{other}"] += 1
    return dict(found) or {"unspecified": 1}


class BedrockGuardrail:
    name: Literal["bedrock", "offline"] = "bedrock"
    label = "Amazon Bedrock Guardrails (ApplyGuardrail)"

    def __init__(self, guardrail_id: str, version: str, region: str, *, client: Any = None) -> None:
        if client is None:
            import boto3
            from botocore.config import Config

            client = boto3.client(
                "bedrock-runtime",
                region_name=region,
                config=Config(retries={"mode": "adaptive", "max_attempts": 4}, connect_timeout=3, read_timeout=15),
            )
        self._client = client
        self._id = guardrail_id
        self._version = version

    async def check(self, source: Source, texts: Sequence[str]) -> None:
        clean = [neutral(t) for t in texts if t and t.strip()]
        for batch in _batches(clean):
            try:
                resp = await asyncio.to_thread(
                    self._client.apply_guardrail,
                    guardrailIdentifier=self._id,
                    guardrailVersion=self._version,
                    source=source,
                    content=[{"text": {"text": t}} for t in batch],
                    outputScope="INTERVENTIONS",
                )
                action = resp["action"]
            except Exception as exc:
                log.warning("backstops.guardrail_failed", error_type=type(exc).__name__)
                raise GuardrailUnavailable("guardrail_unavailable") from None
            if action == "GUARDRAIL_INTERVENED":
                raise GuardrailBlocked(source, kinds_of(resp))
            if action != "NONE":
                raise GuardrailUnavailable("guardrail_unexpected_action")


class OfflineGuardrail:
    name: Literal["bedrock", "offline"] = "offline"
    label = "Offline stand-in for Bedrock Guardrails: Vanimo's own identifier detectors, not a model"

    async def check(self, source: Source, texts: Sequence[str]) -> None:
        found: Counter[str] = Counter()
        for t in texts:
            if t:
                found.update(s.kind for s in detectors.detect(L1_MARKS.sub(" ", t)))
        if found:
            raise GuardrailBlocked(source, dict(found))
