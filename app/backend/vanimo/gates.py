"""The onboarding gate (architecture §6.5, invariant #8).

No message content — bodies, chat text, transcripts — may be fetched for a user until they
have finished or skipped the "Choose what Vanimo learns from" review *for that data source*.
Reviewing the sample workspace never unlocks a real mailbox. Every code path that reads
content must call `require_review_done` first (M2 backfill, M3 live thread, M6 transcripts);
metadata reads (`vanimo.graph.metadata`, the header pass) don't need it.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from vanimo.auth.entra import AuthError
from vanimo.db.session import UserRef, user_tx


class ReviewPending(AuthError):
    def __init__(self) -> None:
        super().__init__("review_pending", 409)


def effective_state(onboarding_state: str, reviewed_source_kind: str | None, source_kind: str) -> str:
    """'review_done' only when the review was completed for the source in use now."""
    if onboarding_state == "review_done" and reviewed_source_kind == source_kind:
        return "review_done"
    return "review_pending"


async def onboarding_state(conn: AsyncConnection, source_kind: str) -> tuple[str, str | None]:
    row = (
        await conn.execute(text("select onboarding_state, review_outcome, reviewed_source_kind from vanimo.users"))
    ).one()
    state = effective_state(row.onboarding_state, row.reviewed_source_kind, source_kind)
    return state, row.review_outcome if state == "review_done" else None


async def require_review_done(engine: AsyncEngine, ref: UserRef, source_kind: str) -> None:
    async with user_tx(engine, ref) as conn:
        state, _ = await onboarding_state(conn, source_kind)
    if state != "review_done":
        raise ReviewPending()
