"""The onboarding gate (architecture §6.5, invariant #8).

No message content — bodies, chat text, transcripts — may be fetched for a user until they
have finished or skipped the "Choose what Vanimo learns from" review *for that data source*.
Reviewing the sample workspace never unlocks a real mailbox. Every code path that reads
content must call `require_review_done` first (M2 backfill, M3 live thread, M6 transcripts);
metadata reads (`vanimo.graph.metadata`, the header pass) don't need it.

The same gate holds while the organisation's pipeline is paused (F11, architecture §7.2 S13: a Macie
finding in an L1 snapshot pauses the tenant until an admin resumes it): no content is read, redacted
or sent to a model, for any source. Settings, data controls and deletion keep working.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from vanimo.auth.entra import AuthError
from vanimo.db.session import UserRef, user_tx


class ReviewPending(AuthError):
    def __init__(self) -> None:
        super().__init__("review_pending", 409)


class PipelinePaused(AuthError):
    def __init__(self) -> None:
        super().__init__("pipeline_paused", 423)


async def pipeline_paused(conn: AsyncConnection) -> bool:
    """Whether the caller's organisation is paused (their own tenant row, under RLS)."""
    return bool(
        (await conn.execute(text("select pipeline_paused_at is not null from vanimo.tenants"))).scalar_one_or_none()
    )


async def require_pipeline_active(conn: AsyncConnection) -> None:
    if await pipeline_paused(conn):
        raise PipelinePaused()


def effective_state(onboarding_state: str, reviewed_sources: list[str] | None, source_kind: str) -> str:
    """'review_done' only when the review was completed for the source in use now."""
    if onboarding_state == "review_done" and source_kind in (reviewed_sources or []):
        return "review_done"
    return "review_pending"


async def onboarding_state(conn: AsyncConnection, source_kind: str) -> tuple[str, str | None]:
    row = (
        await conn.execute(text("select onboarding_state, review_outcome, reviewed_sources from vanimo.users"))
    ).one()
    state = effective_state(row.onboarding_state, row.reviewed_sources, source_kind)
    return state, row.review_outcome if state == "review_done" else None


async def require_review_done(engine: AsyncEngine, ref: UserRef, source_kind: str) -> None:
    async with user_tx(engine, ref) as conn:
        state, _ = await onboarding_state(conn, source_kind)
        await require_pipeline_active(conn)
    if state != "review_done":
        raise ReviewPending()
