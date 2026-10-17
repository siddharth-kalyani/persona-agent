"""Commitments ledger endpoints (MVP plan M5): the promises you made, and follow-ups in your voice.

* GET  /api/commitments               — your promises, in your own view (names back, never-send words
                                         as [removed]), re-checked against your rules as they are now.
* POST /api/commitments/scan          — look for new promises in what you sent since the last scan.
* PUT  /api/commitments/{id}          — done, not a promise, snooze, or reopen.
* POST /api/commitments/{id}/follow-up — a follow-up in your voice (an email reply in the same
                                         conversation, or a message in the same Teams chat). Never sent.
                                         Promises made in a meeting (M6) have no conversation: 409.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from vanimo import audit
from vanimo.api.deps import CurrentPrincipal, CurrentUser, State, UserSource
from vanimo.api.drafting import DraftOut, draft_out
from vanimo.api.learning import self_email
from vanimo.commitments import scan as scanning
from vanimo.commitments.extract import OFFLINE_LABEL
from vanimo.controls.neversend import render_removed
from vanimo.controls.store import load_engine, load_matcher
from vanimo.db.session import user_tx
from vanimo.drafting.context import DraftError
from vanimo.drafting.service import DraftInput, _sample_domains, create_draft
from vanimo.redaction.pipeline import rehydrate

router = APIRouter(prefix="/api", tags=["commitments"])

PRECISION_DAYS = 30


class CommitmentOut(BaseModel):
    id: str
    channel: Literal["email", "chat", "meeting"]
    what: str
    sentence: str
    duePhrase: str | None
    dueAt: datetime | None
    madeAt: datetime
    relationship: str
    status: Literal["open", "done", "dismissed"]
    statusAt: datetime | None
    snoozedUntil: datetime | None
    looksDoneAt: datetime | None  # a later message of yours in the same thread seems to deliver it
    extractor: Literal["offline", "bedrock"]


class LedgerOut(BaseModel):
    items: list[CommitmentOut]
    open: int
    overdue: int
    dueSoon: int  # within the next day
    capturedThisWeek: int
    precision: float | None  # of the promises you decided on (30 days): share that were real
    decided: int
    label: str  # how promises are found (offline stand-in or Claude)
    hidden: int  # stored but excluded by a rule added since (the purge job removes them)


def _excluded(row: Any, engine: Any) -> bool:
    return engine.lineage(
        [(p["p"], list(p["d"])) for p in row.people],
        thread_hash=row.thread_hash if row.channel == "email" else None,
        chat_hash=row.thread_hash if row.channel == "chat" else None,
        meeting_hash=row.meeting_hash,
        series_hash=row.series_hash,
    ).excluded


@router.get("/commitments", response_model=LedgerOut)
async def list_commitments(
    user: CurrentUser,
    principal: CurrentPrincipal,
    source: UserSource,
    state: State,
    status: Literal["open", "done", "dismissed", "all"] = "open",
) -> LedgerOut:
    me = await self_email(source, principal.email)
    v, t, u = state.vault, user.tenant_id, user.user_id
    now = datetime.now(UTC)
    async with user_tx(state.engine, user) as conn:
        engine = await load_engine(conn, v, user, self_email=me, extra_org_domains=_sample_domains(source))
        matcher = await load_matcher(conn, v, user)
        rows = (
            await conn.execute(
                text(
                    "select id, channel, thread_hash, meeting_hash, series_hash, people, relationship, made_at, "
                    "text_enc, what_enc, due_at, due_phrase_enc, status, status_at, snoozed_until, done_hint_at, "
                    "extractor, created_at from vanimo.commitments where source_kind = :k "
                    "order by (due_at is null), due_at, made_at desc limit 500"
                ),
                {"k": source.kind},
            )
        ).all()
        tokens = {
            r.token: v.decrypt_user(t, u, r.value_enc, "l1_token") or ""
            for r in (await conn.execute(text("select token, value_enc from vanimo.l1_tokens"))).all()
        }

    def show(l1: str | None) -> str:
        # Names back for the owner; never-send words as they are now, before the scrub job reaches it.
        return render_removed(matcher.mask(rehydrate(l1 or "", tokens))[0]) or ""

    hidden = 0
    live = []
    for r in rows:
        if _excluded(r, engine):  # logical exclusion: a rule added a moment ago wins before the purge
            hidden += 1
            continue
        live.append(r)
    open_rows = [r for r in live if r.status == "open"]
    awake = [r for r in open_rows if not (r.snoozed_until and r.snoozed_until > now)]
    decided = [
        r
        for r in live
        if r.status in ("done", "dismissed") and r.status_at and r.status_at > now - timedelta(days=PRECISION_DAYS)
    ]
    items = [
        CommitmentOut(
            id=str(r.id),
            channel=r.channel,
            what=show(v.decrypt_user(t, u, r.what_enc, "commitment_what")),
            sentence=show(v.decrypt_user(t, u, r.text_enc, "commitment_text")),
            duePhrase=show(p) if (p := v.decrypt_user(t, u, r.due_phrase_enc, "commitment_due")) else None,
            dueAt=r.due_at,
            madeAt=r.made_at,
            relationship=r.relationship,
            status=r.status,
            statusAt=r.status_at,
            snoozedUntil=r.snoozed_until,
            looksDoneAt=r.done_hint_at,
            extractor=r.extractor,
        )
        for r in live
        if status == "all" or r.status == status
    ]
    return LedgerOut(
        items=items,
        open=len(open_rows),
        overdue=sum(1 for r in awake if r.due_at and r.due_at < now),
        dueSoon=sum(1 for r in awake if r.due_at and now <= r.due_at < now + timedelta(days=1)),
        capturedThisWeek=sum(1 for r in live if r.created_at > now - timedelta(days=7)),
        precision=round(sum(1 for r in decided if r.status == "done") / len(decided), 2) if decided else None,
        decided=len(decided),
        label=OFFLINE_LABEL if state.settings.drafter == "offline" else "Claude on Amazon Bedrock",
        hidden=hidden,
    )


class ScanOut(BaseModel):
    found: int
    hints: int
    read: int
    excluded: int
    pending: bool
    skipped: bool


@router.post("/commitments/scan", response_model=ScanOut)
async def scan_commitments(user: CurrentUser, principal: CurrentPrincipal, source: UserSource, state: State) -> ScanOut:
    me = await self_email(source, principal.email)
    result = await scanning.scan(state, user, source, self_email=me)
    return ScanOut(**scanning.summary(result))


class DecisionIn(BaseModel):
    action: Literal["done", "dismiss", "reopen", "snooze"]
    days: int = Field(1, ge=1, le=14)  # snooze length


@router.put("/commitments/{commitment_id}", status_code=204)
async def decide(
    commitment_id: uuid.UUID, body: DecisionIn, user: CurrentUser, state: State, request: Request
) -> Response:
    status = {"done": "done", "dismiss": "dismissed", "reopen": "open", "snooze": "open"}[body.action]
    snooze = datetime.now(UTC) + timedelta(days=body.days) if body.action == "snooze" else None
    async with user_tx(state.engine, user) as conn:
        row = (
            await conn.execute(
                text(
                    "update vanimo.commitments set status = :s, status_at = case when :s = 'open' then null else now() "
                    "end, snoozed_until = :z where id = :id returning id"
                ),
                {"s": status, "z": snooze, "id": commitment_id},
            )
        ).first()
        if row is None:
            raise DraftError("not_found", 404)
        await audit.record(
            conn,
            user,
            f"commitment.{body.action}",
            target_kind="commitment",
            target_ref=str(commitment_id),
            request_id=request.state.request_id,
        )
    return Response(status_code=204)


class FollowUpIn(BaseModel):
    kind: Literal["done", "late", "update"]
    newDate: str | None = Field(None, max_length=40)  # as the user wants it written ("Monday", "21 Oct")
    note: str | None = Field(None, max_length=500)
    quality: Literal["auto", "standard", "premium"] = "auto"


def instruction(kind: str, what: str, new_date: str | None, note: str | None) -> str:
    """The follow-up asked of the drafter, in the user's own terms (L0; redacted like any instruction)."""
    w = what[:1].lower() + what[1:]
    if kind == "done":
        text_ = f"tell them that this is done, as promised: {w} [add the link or attachment]"
    elif kind == "late":
        text_ = f"apologise for the delay on this: {w}; " + (
            f"tell them that I will have it done by {new_date}"
            if new_date
            else "tell them that I'll share a new date soon"
        )
    else:
        text_ = f"tell them that I'm still on it: {w}; " + (
            f"tell them that I will update them by {new_date}"
            if new_date
            else "tell them that I will update them shortly"
        )
    return f"{text_}; {note.strip()}" if note and note.strip() else text_


@router.post("/commitments/{commitment_id}/follow-up", response_model=DraftOut)
async def follow_up(
    commitment_id: uuid.UUID,
    body: FollowUpIn,
    user: CurrentUser,
    principal: CurrentPrincipal,
    source: UserSource,
    state: State,
    request: Request,
) -> DraftOut:
    """Drafted where the promise was made. The drafting service checks the conversation or chat
    against your rules again (metadata first), so an excluded one is refused like any draft."""
    me = await self_email(source, principal.email)
    v, t, u = state.vault, user.tenant_id, user.user_id
    async with user_tx(state.engine, user) as conn:
        r = (
            await conn.execute(
                text(
                    "select id, channel, ref_enc, what_enc, status from vanimo.commitments "
                    "where id = :id and source_kind = :k"
                ),
                {"id": commitment_id, "k": source.kind},
            )
        ).first()
        tokens = {
            row.token: v.decrypt_user(t, u, row.value_enc, "l1_token") or ""
            for row in (await conn.execute(text("select token, value_enc from vanimo.l1_tokens"))).all()
        }
    if r is None:
        raise DraftError("not_found", 404)
    ref = v.decrypt_user(t, u, r.ref_enc, "commitment_ref")
    if not ref:
        raise DraftError("no_conversation", 409)
    what = rehydrate(v.decrypt_user(t, u, r.what_enc, "commitment_what") or "", tokens)
    req = DraftInput(
        mode="new" if r.channel == "chat" else "reply",
        surface="commitments",
        conversation_id=ref,
        instruction=instruction(body.kind, what, body.newDate, body.note),
        quality=body.quality,
        channel=r.channel,
    )
    result = await create_draft(state, user, source, self_email=me, req=req, request_id=request.state.request_id)
    return draft_out(result)
