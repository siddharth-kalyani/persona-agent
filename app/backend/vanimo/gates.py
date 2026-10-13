"""The onboarding gate (architecture §6.5, invariant #8).

No message content — bodies, chat text, transcripts — may be fetched for a user until they
have finished or skipped the "Choose what Vanimo learns from" review. Every code path that
reads content must call `require_review_done` first (M2 backfill, M3 live thread, M6
transcripts); metadata reads (`vanimo.graph.metadata`) don't need it.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from vanimo.auth.entra import AuthError
from vanimo.db.session import UserRef, user_tx


class ReviewPending(AuthError):
    def __init__(self) -> None:
        super().__init__("review_pending", 409)


async def require_review_done(engine: AsyncEngine, ref: UserRef) -> None:
    async with user_tx(engine, ref) as conn:
        state = (await conn.execute(text("select onboarding_state from vanimo.users"))).scalar_one_or_none()
    if state != "review_done":
        raise ReviewPending()
