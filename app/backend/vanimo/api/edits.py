"""The edit loop (MVP plan M4): what you changed in Vanimo's drafts, and the rules learned from it.

* POST /api/edits/sync          — match your pending drafts to what you actually sent.
* POST /api/drafts/{id}/sent    — sample workspace only: "Mark as sent" with your final text.
* GET  /api/edits/summary       — send-without-edit rate (the north star) and friends.
* GET  /api/rules               — rules learned from your edits, to keep or reject.
* PUT  /api/rules/{id}          — keep (confirm), not me (reject), or stop using a kept rule.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

from vanimo import audit
from vanimo.api.deps import CurrentPrincipal, CurrentUser, State, UserSource
from vanimo.api.learning import self_email
from vanimo.db.session import user_tx
from vanimo.drafting.context import DraftError
from vanimo.edits import matching, rules

router = APIRouter(prefix="/api", tags=["edits"])

SYNC_EVERY_S = 60.0  # per user: the queue and persona pages call sync on load
_last_sync: dict[str, float] = {}


class SyncOut(BaseModel):
    matched: int
    unmatched: int
    excluded: int
    skipped: bool  # synced less than a minute ago


@router.post("/edits/sync", response_model=SyncOut)
async def sync(user: CurrentUser, principal: CurrentPrincipal, source: UserSource, state: State) -> SyncOut:
    key = f"{user.user_id}:{source.kind}"
    if time.monotonic() - _last_sync.get(key, -SYNC_EVERY_S) < SYNC_EVERY_S:
        return SyncOut(matched=0, unmatched=0, excluded=0, skipped=True)
    _last_sync[key] = time.monotonic()
    if len(_last_sync) > 10_000:
        _last_sync.clear()
    me = await self_email(source, principal.email)
    async with user_tx(state.engine, user) as conn:
        from vanimo.gates import onboarding_state

        onboarding, _ = await onboarding_state(conn, source.kind)
    if onboarding != "review_done":
        raise DraftError("review_pending", 409)
    counts = await matching.sync(state, user, source, self_email=me)
    return SyncOut(matched=counts["matched"], unmatched=counts["unmatched"], excluded=counts["excluded"], skipped=False)


class SentIn(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)


class SentOut(BaseModel):
    outcome: str
    editShare: float
    edits: list[str]  # kinds only


@router.post("/drafts/{draft_id}/sent", response_model=SentOut)
async def mark_sent(
    draft_id: uuid.UUID,
    body: SentIn,
    user: CurrentUser,
    principal: CurrentPrincipal,
    source: UserSource,
    state: State,
    request: Request,
) -> SentOut:
    """Sample workspace only: your edited text stands in for the email you sent. It is compared in
    memory with the draft; only the outcome and the kinds of edit are kept."""
    me = await self_email(source, principal.email)
    c = await matching.record_sent(state, user, source, self_email=me, draft_id=str(draft_id), sent_text=body.text)
    async with user_tx(state.engine, user) as conn:
        await audit.record(
            conn,
            user,
            "draft.marked_sent",
            target_kind="draft",
            target_ref=str(draft_id),
            request_id=request.state.request_id,
        )
    return SentOut(outcome=c.outcome, editShare=c.edit_share, edits=sorted({e.kind for e in c.edits}))


@router.get("/edits/summary")
async def summary(user: CurrentUser, source: UserSource, state: State) -> dict[str, Any]:
    async with user_tx(state.engine, user) as conn:
        rows = (
            await conn.execute(
                text("select outcome, edit_share, relationship from vanimo.edit_events where source_kind = :k"),
                {"k": source.kind},
            )
        ).all()
        tracked = (
            await conn.execute(
                text("select match_state, count(*) as n from vanimo.drafts where source_kind = :k group by 1"),
                {"k": source.kind},
            )
        ).all()
    return {
        **rules.summarise([(r.outcome, r.edit_share, r.relationship) for r in rows]),
        "drafts": {r.match_state: r.n for r in tracked},
    }


class RuleOut(BaseModel):
    id: str
    scope: str
    kind: str
    value: str  # forms keep their placeholders ({first}, {me}); phrases in your own words
    text: str
    status: Literal["candidate", "active", "confirmed", "rejected"]
    evidence: int
    contradictions: int
    support: float | None
    lastSeen: datetime


@router.get("/rules", response_model=list[RuleOut])
async def list_rules(user: CurrentUser, source: UserSource, state: State) -> list[RuleOut]:
    from vanimo.controls.neversend import render_removed

    async with user_tx(state.engine, user) as conn:
        found = await rules.load_rules(conn, state.vault, user, source.kind)
    return [
        RuleOut(
            id=r.id,
            scope=r.scope,
            kind=r.kind,
            value=render_removed(r.value) or "",
            text=render_removed(r.text) or "",
            status=r.status,  # type: ignore[arg-type]
            evidence=r.evidence,
            contradictions=r.contradictions,
            support=r.support,
            lastSeen=r.last_seen,
        )
        for r in found
    ]


class DecisionIn(BaseModel):
    decision: Literal["keep", "reject"]


@router.put("/rules/{rule_id}", response_model=RuleOut)
async def decide(
    rule_id: uuid.UUID, body: DecisionIn, user: CurrentUser, source: UserSource, state: State, request: Request
) -> RuleOut:
    """Keep → confirmed (used in every draft for this audience). Reject → never used or proposed
    again. A candidate can't be kept before it has enough evidence."""
    status = "confirmed" if body.decision == "keep" else "rejected"
    async with user_tx(state.engine, user) as conn:
        row = (
            await conn.execute(
                text(
                    "update vanimo.style_rules set status = :s, decided_at = now() where id = :id "
                    "and (:s = 'rejected' or status in ('active', 'confirmed')) returning id"
                ),
                {"s": status, "id": rule_id},
            )
        ).first()
        if row is None:
            raise DraftError("rule_not_ready", 409)
        await audit.record(
            conn,
            user,
            f"rule.{status}",
            target_kind="rule",
            target_ref=str(rule_id),
            request_id=request.state.request_id,
        )
        found = [r for r in await rules.load_rules(conn, state.vault, user, source.kind) if r.id == str(rule_id)]
    if not found:
        raise DraftError("not_found", 404)
    r = found[0]
    return RuleOut(
        id=r.id, scope=r.scope, kind=r.kind, value=r.value, text=r.text, status=r.status,  # type: ignore[arg-type]
        evidence=r.evidence, contradictions=r.contradictions, support=r.support, lastSeen=r.last_seen,
    )  # fmt: skip
