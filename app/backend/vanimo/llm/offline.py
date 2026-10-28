"""Offline stand-in for the Claude drafter (D7: AWS account arrives after all milestones).

Builds a reply without any model: greeting and sign-off sampled from the user's style card
(their most common form), and the body of their most similar past reply (exemplar retrieval
over the local vector stand-in). It is clearly labelled wherever it is shown, and is the
baseline the real Haiku 5.5 drafter must beat in the M2/M3 evaluations. Input and output are L1.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from vanimo.learning import style
from vanimo.learning.embed import cosine, embed

LABEL = "Offline stand-in (no AI model): style card + closest past reply"


@dataclass(frozen=True)
class Exemplar:
    id: str
    text: str  # L1 reply
    context: str | None  # L1 message it replied to
    tone: str
    bucket: str
    vec: list[float] | None


@dataclass(frozen=True)
class Draft:
    text: str
    exemplar_ids: list[str]
    card_slice: str | None
    label: str = LABEL


def nearest(
    incoming: str, pool: Sequence[Exemplar], *, tone: str, bucket: str, k: int = 3
) -> list[tuple[float, Exemplar]]:
    """Top-k past replies by similarity of what they replied to; the same tone and channel preferred (a
    small bonus), never required."""
    q = embed(incoming)
    scored = []
    for ex in pool:
        v = ex.vec or embed(ex.context or "")
        bonus = (0.15 if ex.tone == tone else 0) + (0.1 if ex.bucket == bucket else 0)
        scored.append((cosine(q, v) + bonus, ex))
    scored.sort(key=lambda s: -s[0])
    return scored[:k]


def _top(dist: list[list[Any]]) -> str | None:
    for value, _share in dist:
        if value != "(none)":
            return str(value)
    return None


class OfflineDrafter:
    def draft(
        self,
        incoming: str,
        *,
        tone: str,
        bucket: str,
        cards: dict[str, dict[str, Any]],
        pool: Sequence[Exemplar],
        language: str = "*",
    ) -> Draft:
        found = style.channel_card(cards, tone, bucket, language)
        card_key, card = found if found else (None, {})
        best = nearest(incoming, pool, tone=tone, bucket=bucket)
        body = style.body_lines(best[0][1].text) if best else ""
        parts: list[str] = []
        if card and card["greetings"] and card["greetings"][0][0] != "(none)":
            parts.append(_top(card["greetings"]) or "")
        if body:
            parts.append(body)
        if card and (sign := _top(card["sign_offs"])) and card["sign_offs"][0][0] != "(none)":
            # The card keeps the form ("Thanks,\n{me}"); a draft carries the user's own token, as the
            # messages it's compared with do, so sign-offs are recognised and matched on both sides.
            parts.append(sign.replace("{me_full}", "⟦ME.full⟧").replace("{me}", "⟦ME⟧"))
        return Draft("\n\n".join(p for p in parts if p), [b[1].id for b in best[:1]], card_key)
