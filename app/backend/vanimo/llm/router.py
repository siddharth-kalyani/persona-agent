"""Model router and Bedrock client (D7: Claude on Amazon Bedrock only).

Haiku by default; Sonnet for premium drafts (new emails, long replies, external or
executive audiences). Every model must be on the cell's allow-list, which is how
inference residency is enforced per tenant later (architecture §9.1).
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from anthropic import AsyncAnthropicBedrockMantle

from vanimo.config import Settings

Tier = Literal["default", "premium"]
Quality = Literal["auto", "standard", "premium"]

# Replies longer than this (target words) go to the premium model when quota allows.
LONG_DRAFT_WORDS = 180


class ModelNotAllowed(Exception):
    pass


@dataclass(frozen=True)
class StreamTiming:
    model_id: str
    ttft_ms: float | None
    total_ms: float
    output_chars: int


@dataclass(frozen=True)
class Route:
    tier: Tier
    model_id: str
    reason: str  # content-free: why this tier


@dataclass(frozen=True)
class Generated:
    text: str
    model_id: str
    ttft_ms: float | None
    total_ms: float


class ModelRouter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._allowed = frozenset(settings.cell_config.model_allow_list)

    def model_for(self, tier: Tier) -> str:
        model = self._settings.model_premium if tier == "premium" else self._settings.model_default
        return self.check(model)

    def check(self, model: str) -> str:
        if model not in self._allowed:
            raise ModelNotAllowed(model)
        return model

    def route_draft(
        self, *, mode: str, relationship: str, target_words: int, quality: Quality, premium_used_today: int
    ) -> Route:
        """Haiku unless the draft is worth Sonnet and the user's daily premium quota allows it:
        the user asked for higher quality, a new email to a client or the manager, or a long reply."""
        quota_left = premium_used_today < self._settings.premium_drafts_per_day
        if quality == "standard":
            return Route("default", self.model_for("default"), "asked_standard")
        if quality == "premium":
            if quota_left:
                return Route("premium", self.model_for("premium"), "asked_premium")
            return Route("default", self.model_for("default"), "premium_quota_used")
        if quota_left and mode == "new" and relationship in ("external", "manager"):
            return Route("premium", self.model_for("premium"), f"new_to_{relationship}")
        if quota_left and target_words > LONG_DRAFT_WORDS:
            return Route("premium", self.model_for("premium"), "long_draft")
        return Route("default", self.model_for("default"), "default")


class LlmClient:
    def __init__(self, settings: Settings, router: ModelRouter) -> None:
        self._router = router
        self._client = AsyncAnthropicBedrockMantle(aws_region=settings.cell_config.bedrock_region)

    async def stream_text(
        self, *, model: str, system: str | Sequence[dict[str, Any]], user_text: str, max_tokens: int = 2048
    ) -> AsyncIterator[str]:
        """Stream plain text. `user_text` must already be L1 (redacted) — callers own that."""
        async for text in self._stream(model, system, [{"role": "user", "content": user_text}], max_tokens):
            yield text

    async def _stream(
        self, model: str, system: str | Sequence[dict[str, Any]], messages: list[dict[str, Any]], max_tokens: int
    ) -> AsyncIterator[str]:
        self._router.check(model)
        async with self._client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system,  # type: ignore[arg-type]
            messages=messages,  # type: ignore[arg-type]
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def generate(
        self,
        *,
        model: str,
        system: str | Sequence[dict[str, Any]],
        messages: list[dict[str, Any]],
        max_tokens: int = 1024,
    ) -> Generated:
        """One complete answer (streamed internally for time to first token). Every message must
        already be L1; the drafting output gate runs on the whole text before anyone sees it."""
        start = time.perf_counter()
        first: float | None = None
        parts: list[str] = []
        async for chunk in self._stream(model, system, messages, max_tokens):
            if first is None and chunk:
                first = time.perf_counter()
            parts.append(chunk)
        end = time.perf_counter()
        return Generated(
            text="".join(parts),
            model_id=model,
            ttft_ms=None if first is None else round((first - start) * 1000, 1),
            total_ms=round((end - start) * 1000, 1),
        )

    async def timed_probe(self, model: str, prompt: str, max_tokens: int = 64) -> StreamTiming:
        """Latency probe with a synthetic prompt (no user content). Used by diagnostics."""
        start = time.perf_counter()
        first: float | None = None
        chars = 0
        async for chunk in self.stream_text(
            model=model, system="Reply briefly.", user_text=prompt, max_tokens=max_tokens
        ):
            if first is None and chunk:
                first = time.perf_counter()
            chars += len(chunk)
        end = time.perf_counter()
        return StreamTiming(
            model_id=model,
            ttft_ms=None if first is None else round((first - start) * 1000, 1),
            total_ms=round((end - start) * 1000, 1),
            output_chars=chars,
        )
