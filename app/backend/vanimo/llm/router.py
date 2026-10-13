"""Model router and Bedrock client (D7: Claude on Amazon Bedrock only).

Haiku by default; Sonnet for premium drafts (new emails, long replies, external or
executive audiences). Every model must be on the cell's allow-list, which is how
inference residency is enforced per tenant later (architecture §9.1).
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

from anthropic import AsyncAnthropicBedrockMantle

from vanimo.config import Settings

Tier = Literal["default", "premium"]


class ModelNotAllowed(Exception):
    pass


@dataclass(frozen=True)
class StreamTiming:
    model_id: str
    ttft_ms: float | None
    total_ms: float
    output_chars: int


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


class LlmClient:
    def __init__(self, settings: Settings, router: ModelRouter) -> None:
        self._router = router
        self._client = AsyncAnthropicBedrockMantle(aws_region=settings.cell_config.bedrock_region)

    async def stream_text(
        self, *, model: str, system: str, user_text: str, max_tokens: int = 2048
    ) -> AsyncIterator[str]:
        """Stream plain text. `user_text` must already be L1 (redacted) — callers own that."""
        self._router.check(model)
        async with self._client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_text}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

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
