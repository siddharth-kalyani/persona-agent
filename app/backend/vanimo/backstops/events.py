"""What the backstops caught, content-free (`vanimo.backstop_events`, migration 0014).

A guardrail block happens deep inside a model call, which doesn't know who it is for: the API binds
the acting user here (`ACTING_USER`, set with the request's identity and inherited by the background
tasks a request starts), and the recorder writes the event as that user. Recording never changes the
outcome: the call is blocked whether or not the event could be written.
"""

from __future__ import annotations

import json
import re
from contextvars import ContextVar
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from vanimo.db.session import UserRef, user_tx
from vanimo.logs import get_logger

log = get_logger("vanimo.backstops")

ACTING_USER: ContextVar[UserRef | None] = ContextVar("vanimo_acting_user", default=None)

Source = Literal["comprehend", "guardrail", "macie"]
Stage = Literal["redaction", "model_input", "model_output", "snapshot"]
Outcome = Literal["blocked", "finding", "unavailable"]
_KIND = re.compile(r"^[A-Za-z0-9_:. \-]{1,60}$")


def clean_kinds(kinds: dict[str, int]) -> dict[str, int]:
    """Entity type names and counts only; anything else (a value that slipped in) is dropped."""
    return {k: int(n) for k, n in list(kinds.items())[:40] if isinstance(k, str) and _KIND.match(k)}


async def record(
    engine: AsyncEngine,
    *,
    source: Source,
    stage: Stage,
    outcome: Outcome,
    kinds: dict[str, int],
    ref: UserRef | None = None,
) -> None:
    ref = ref or ACTING_USER.get()
    log.warning("backstops.event", source=source, stage=stage, outcome=outcome, count=sum(clean_kinds(kinds).values()))
    if ref is None:
        return
    try:
        async with user_tx(engine, ref) as conn:
            await conn.execute(
                text(
                    "insert into vanimo.backstop_events (tenant_id, user_id, source, stage, outcome, kinds) "
                    "values (:t, :u, :s, :st, :o, cast(:k as jsonb))"
                ),
                {
                    "t": ref.tenant_id,
                    "u": ref.user_id,
                    "s": source,
                    "st": stage,
                    "o": outcome,
                    "k": json.dumps(clean_kinds(kinds)),
                },
            )
    except Exception as exc:
        log.warning("backstops.record_failed", error_type=type(exc).__name__)
