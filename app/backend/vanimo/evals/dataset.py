"""Eval cases: brief-conditioned reconstruction of held-out sent messages.

Each case is an L1 (already redacted) thread context, a short brief of what the user
wanted to say, and the message they actually sent. Cases are time-split per user so
the persona is built only from messages sent *before* the held-out ones.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EvalCase:
    id: str
    slice: str  # relationship/intent/channel, e.g. "manager/reply/email"
    brief: str
    context_l1: str
    reference_sent_l1: str


def load_jsonl(path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    with path.open(encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            try:
                cases.append(EvalCase(**row))
            except TypeError as exc:
                raise ValueError(f"{path.name}:{n}: {exc}") from exc
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{path.name}: duplicate case ids")
    return cases
