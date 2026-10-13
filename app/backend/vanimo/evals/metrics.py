"""Persona-quality metrics (architecture §9.5, MVP exit criteria in docs/03 §5).

North star: minimal-edit send rate. A draft "needs no edit" when the user would change
≤ 5% of its characters to get what they actually sent; "light edit" is < 20%.
"""

from __future__ import annotations

from dataclasses import dataclass

SEND_WITHOUT_EDIT_MAX = 0.05
LIGHT_EDIT_MAX = 0.20


def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def edit_ratio(draft: str, sent: str) -> float:
    """Characters changed to turn the draft into what was sent, relative to the longer text."""
    draft, sent = draft.strip(), sent.strip()
    longest = max(len(draft), len(sent))
    return 0.0 if longest == 0 else levenshtein(draft, sent) / longest


def bucket(ratio: float) -> str:
    if ratio <= SEND_WITHOUT_EDIT_MAX:
        return "sent_as_is"
    if ratio < LIGHT_EDIT_MAX:
        return "light_edit"
    return "heavy_edit"


@dataclass(frozen=True)
class Gate:
    """MVP exit gate (docs/03 §5): ≥ 25% send-without-edit and ≥ 55% light-or-better."""

    send_without_edit_min: float = 0.25
    light_or_better_min: float = 0.55

    def passes(self, send_without_edit: float, light_or_better: float) -> bool:
        return send_without_edit >= self.send_without_edit_min and light_or_better >= self.light_or_better_min
