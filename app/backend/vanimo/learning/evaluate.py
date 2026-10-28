"""Offline style evaluation baseline (MVP plan M2 "eval baseline").

Held-out replies (a deterministic ~15 % by item hash) are re-drafted from what they replied to,
using only the rest of the user's history, and compared with what the user actually wrote.
Metrics are numbers only — no text leaves this function — and are stored per run, so later
milestones (the real Claude drafter, edit learning) can show they beat this baseline.
"""

from __future__ import annotations

import itertools
import json
import statistics
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from vanimo.db.session import UserRef, user_tx
from vanimo.learning import style
from vanimo.learning.persona import examples, load_items
from vanimo.llm.offline import Exemplar, OfflineDrafter
from vanimo.vault import Vault


def _bigrams(t: str) -> set[str]:
    ws = style._words(t)
    return {f"{a} {b}" for a, b in itertools.pairwise(ws)}


def _ratio(a: int, b: int) -> float:
    return min(a, b) / max(a, b) if max(a, b) else 1.0


def score(draft: str, actual: str) -> dict[str, float]:
    da, aa = style.body_lines(draft) or draft, style.body_lines(actual) or actual
    ba, bb = _bigrams(da), _bigrams(aa)
    return {
        "greeting_match": float(style.greeting_of(draft) == style.greeting_of(actual)),
        "sign_off_match": float(style.sign_off_of(draft) == style.sign_off_of(actual)),
        "length_ratio": _ratio(len(style._words(da)), len(style._words(aa))),
        "bigram_overlap": len(ba & bb) / len(ba | bb) if ba | bb else 1.0,
    }


async def offline_baseline(engine: AsyncEngine, vault: Vault, ref: UserRef, source_kind: str) -> dict[str, Any]:
    async with user_tx(engine, ref) as conn:
        items = await load_items(conn, vault, ref, source_kind)
    train = [i for i in items if not i.held_out]
    test = [i for i in items if i.held_out and i.context]
    metrics: dict[str, Any] = {"n_train": len(train), "n_eval": len(test), "drafter": "offline_stand_in"}
    if train and test:
        cards = {k: c for k, (_, c) in style.build_cards(examples(train)).items()}
        pool = [Exemplar(i.id, i.text, i.context, i.tone, i.bucket, i.vec) for i in train]
        drafter = OfflineDrafter()
        scores = [
            score(
                drafter.draft(
                    t.context or "",
                    tone=t.tone,
                    bucket=t.bucket,
                    cards=cards,
                    pool=pool,
                    language=t.language,
                ).text,
                t.text,
            )
            for t in test
        ]
        for key in scores[0]:
            metrics[key] = round(statistics.mean(s[key] for s in scores), 3)
    async with user_tx(engine, ref) as conn:
        await conn.execute(
            text(
                "insert into vanimo.eval_runs (tenant_id, owner_user_id, source_kind, kind, metrics) "
                "values (:t, :u, :k, 'offline_baseline', cast(:m as jsonb))"
            ),
            {"t": ref.tenant_id, "u": ref.user_id, "k": source_kind, "m": json.dumps(metrics)},
        )
    return metrics
