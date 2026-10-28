"""Learning, persona and sample-workspace endpoints (MVP plan M2).

* /api/learning      — start a backfill (gate-checked), see progress and what was stored, and
                       delete everything learned (with a purge receipt).
* /api/persona       — the Persona Snapshot, the basic studio settings, and the tone of each
                       conversation (the user may change it: F15 tone groups).
* /api/sample/...    — the synthetic mailbox, chats and meetings as Outlook/Teams would show
                       them, with what Vanimo did with each item. Sample workspace only.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from vanimo import audit
from vanimo.api.deps import CurrentPrincipal, CurrentUser, State, UserSource
from vanimo.commitments.scan import extractor_for
from vanimo.controls.jobs import run_job
from vanimo.controls.store import add_purge_job, hasher_for, load_engine
from vanimo.db.session import UserRef, user_tx
from vanimo.gates import onboarding_state, require_pipeline_active
from vanimo.learning import backfill, tone_store, tones, vocab
from vanimo.learning.persona import PersonaSettings, rebuild, save_settings, snapshot
from vanimo.redaction.pipeline import rehydrate
from vanimo.sources.base import WorkspaceSource
from vanimo.state import AppState

router = APIRouter(prefix="/api", tags=["learning"])


async def self_email(source: WorkspaceSource, principal_email: str | None) -> str:
    """The mailbox owner's address: the directory profile first, the sign-in name otherwise."""
    profile = await source.profile()
    email = profile.email or principal_email
    if not email:
        raise HTTPException(409, detail={"error": "mailbox_address_unknown"})
    return email.lower()


# --- learning -----------------------------------------------------------------------------------
class RunOut(BaseModel):
    id: str
    status: str
    sourceKind: str
    startedAt: datetime
    finishedAt: datetime | None
    counts: dict[str, Any]
    errorCode: str | None


class LearningOut(BaseModel):
    onboardingState: str
    sourceKind: str
    run: RunOut | None
    stored: dict[str, int]
    styleCards: int
    # F15: whether drafting may start (a finished run of this version whose result is still stored), and
    # whether the last finished run predates tone groups (learn again).
    learned: bool = False
    outdated: bool = False


async def _learning(state: AppState, user: UserRef, kind: str) -> LearningOut:
    async with user_tx(state.engine, user) as conn:
        onboarding, _ = await onboarding_state(conn, kind)
        run = (
            await conn.execute(
                text(
                    "select id, status, source_kind, started_at, finished_at, counts, error_code "
                    "from vanimo.learning_runs where source_kind = :k order by started_at desc limit 1"
                ),
                {"k": kind},
            )
        ).first()
        stored = (
            await conn.execute(
                text("select channel, count(*) as n from vanimo.l1_items where source_kind = :k group by channel"),
                {"k": kind},
            )
        ).all()
        cards = (
            await conn.execute(
                text("select count(*) from vanimo.style_cards where source_kind = :k and slice not like '@%'"),
                {"k": kind},
            )
        ).scalar_one()
        learning = await backfill.learning_state(conn, kind)
    counts = {r.channel: r.n for r in stored}
    return LearningOut(
        onboardingState=onboarding,
        sourceKind=kind,
        run=RunOut(
            id=str(run.id),
            status=run.status,
            sourceKind=run.source_kind,
            startedAt=run.started_at,
            finishedAt=run.finished_at,
            counts=run.counts,
            errorCode=run.error_code,
        )
        if run
        else None,
        stored={"email": counts.get("email", 0), "chat": counts.get("chat", 0), "total": sum(counts.values())},
        styleCards=cards,
        learned=learning.learned,
        outdated=learning.outdated,
    )


@router.get("/learning", response_model=LearningOut)
async def learning_status(user: CurrentUser, source: UserSource, state: State) -> LearningOut:
    return await _learning(state, user, source.kind)


@router.post("/learning/run", response_model=LearningOut, status_code=202)
async def start_learning(
    user: CurrentUser, principal: CurrentPrincipal, source: UserSource, state: State, request: Request
) -> LearningOut:
    """Starts the backfill in the background; poll GET /learning. Sample workspaces finish in seconds."""
    async with user_tx(state.engine, user) as conn:
        onboarding, _ = await onboarding_state(conn, source.kind)
        await require_pipeline_active(conn)
    if onboarding != "review_done":
        raise HTTPException(409, detail={"error": "review_pending"})
    email = await self_email(source, principal.email)
    try:
        run_id = await backfill.start_run(state.engine, user, source.kind)
    except backfill.LearningRunning:
        raise HTTPException(409, detail={"error": "learning_running"}) from None
    background = getattr(source, "for_background", None)
    task = state.spawn(
        backfill.run_learning(
            state.engine,
            state.vault,
            user,
            background() if background else source,
            self_email=email,
            run_id=run_id,
            extractor=extractor_for(state),
            tz=state.settings.cell_config.zone,
            tone_judge=tone_judge_for(state),
            vocab_extractor=vocab_for(state),
        )
    )
    async with user_tx(state.engine, user) as conn:
        await audit.record(
            conn,
            user,
            "learning.started",
            target_kind="learning_run",
            target_ref=run_id,
            request_id=request.state.request_id,
        )
    if source.kind == "sample":
        await asyncio.gather(task, return_exceptions=True)  # the outcome is on the run row
    return await _learning(state, user, source.kind)


def tone_judge_for(state: AppState) -> tones.ToneJudge:
    """Claude judges tones and reads vocabulary when the drafter is Bedrock; the offline rules otherwise."""
    return tones.BedrockJudge(state.llm, state.router) if state.settings.drafter == "bedrock" else tones.OfflineJudge()


def vocab_for(state: AppState) -> vocab.Extractor:
    if state.settings.drafter == "bedrock":
        return vocab.BedrockExtractor(state.llm, state.router)
    return vocab.OfflineExtractor()


class PurgeOut(BaseModel):
    jobId: str
    status: str
    counts: dict[str, Any]


@router.delete("/learning", response_model=PurgeOut)
async def delete_learning(user: CurrentUser, state: State, request: Request) -> PurgeOut:
    """Delete everything learned (all sources). Returns the purge receipt."""
    async with user_tx(state.engine, user) as conn:
        job_id = await add_purge_job(conn, user, "learning_deleted")
        await audit.record(
            conn,
            user,
            "learning.deleted",
            target_kind="purge_job",
            target_ref=job_id,
            request_id=request.state.request_id,
        )
    await run_job(state.engine, state.vault, user, job_id, "learning_deleted")
    async with user_tx(state.engine, user) as conn:
        row = (
            await conn.execute(text("select status, counts from vanimo.purge_jobs where id = :id"), {"id": job_id})
        ).one()
    return PurgeOut(jobId=job_id, status=row.status, counts=row.counts)


class StoredItemOut(BaseModel):
    id: str
    channel: str
    sentAt: datetime
    relationship: str
    intent: str
    language: str
    wordCount: int
    bucket: str
    tone: str
    situations: list[str]
    heldOut: bool
    suspicious: bool
    subject: str | None
    stored: str  # L1 exactly as stored (tokens, slots, placeholders)
    display: str  # L1 re-hydrated for the owner (names back; never-send as [removed]; slots stay)
    contextStored: str | None
    contextDisplay: str | None


class StoredItemsOut(BaseModel):
    items: list[StoredItemOut]
    total: int


async def _token_values(conn: Any, state: AppState, user: UserRef) -> dict[str, str]:
    rows = (await conn.execute(text("select token, value_enc from vanimo.l1_tokens"))).all()
    return {
        r.token: state.vault.decrypt_user(user.tenant_id, user.user_id, r.value_enc, "l1_token") or "" for r in rows
    }


@router.get("/learning/items", response_model=StoredItemsOut)
async def stored_items(
    user: CurrentUser,
    source: UserSource,
    state: State,
    channel: Literal["email", "chat"] | None = None,
    ids: list[uuid.UUID] = Query(default_factory=list, max_length=100),  # noqa: B008
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> StoredItemsOut:
    """What Vanimo stored, in the owner's own view. Only the owner can read this (RLS)."""
    v, t, u = state.vault, user.tenant_id, user.user_id
    where = "source_kind = :k" + (" and channel = :ch" if channel else "") + (" and id = any(:ids)" if ids else "")
    params: dict[str, Any] = {"k": source.kind, "ch": channel, "ids": ids, "lim": limit, "off": offset}
    async with user_tx(state.engine, user) as conn:
        total = (await conn.execute(text(f"select count(*) from vanimo.l1_items where {where}"), params)).scalar_one()  # noqa: S608
        rows = (
            await conn.execute(
                text(
                    "select id, channel, sent_at, relationship, intent, language, word_count, held_out, suspicious, "  # noqa: S608 - fixed clauses, values bound
                    f"bucket, tone, situations, subject_enc, text_enc, context_enc from vanimo.l1_items where {where} "
                    "order by sent_at desc limit :lim offset :off"
                ),
                params,
            )
        ).all()
        tokens = await _token_values(conn, state, user)
    items = []
    for r in rows:
        body = v.decrypt_user(t, u, r.text_enc, "l1_text") or ""
        ctx = v.decrypt_user(t, u, r.context_enc, "l1_context")
        subj = v.decrypt_user(t, u, r.subject_enc, "l1_subject")
        items.append(
            StoredItemOut(
                id=str(r.id),
                channel=r.channel,
                sentAt=r.sent_at,
                relationship=r.relationship,
                intent=r.intent,
                language=r.language,
                wordCount=r.word_count,
                bucket=r.bucket,
                tone=r.tone,
                situations=list(r.situations or ()),
                heldOut=r.held_out,
                suspicious=r.suspicious,
                subject=rehydrate(subj, tokens) if subj else None,
                stored=body,
                display=rehydrate(body, tokens),
                contextStored=ctx,
                contextDisplay=rehydrate(ctx, tokens) if ctx else None,
            )
        )
    return StoredItemsOut(items=items, total=total)


# --- persona ------------------------------------------------------------------------------------
@router.get("/persona")
async def get_persona(user: CurrentUser, source: UserSource, state: State) -> dict[str, Any]:
    return await snapshot(state.engine, state.vault, user, source.kind)


class ToneIn(BaseModel):
    bucket: Literal["email", "dm", "group"]
    key: str = Field(pattern="^[0-9a-f]{64}$")
    tone: Literal["formal", "friendly", "casual"] | None  # None: back to what Vanimo judged


@router.put("/persona/tones", status_code=204)
async def put_tone(body: ToneIn, user: CurrentUser, source: UserSource, state: State, request: Request) -> Response:
    """The user's own choice of tone for one conversation. It wins over what was judged and survives learning
    again; the learned messages of that conversation move to the chosen tone at once (cards rebuilt)."""
    async with user_tx(state.engine, user) as conn:
        if not await tone_store.set_override(conn, source.kind, body.bucket, body.key, body.tone):
            raise HTTPException(404, detail={"error": "not_found"})
        effective = (
            body.tone
            or (
                await conn.execute(
                    text(
                        "select tone from vanimo.conversation_tones where source_kind = :k and bucket = :b "
                        "and key_hash = :key"
                    ),
                    {"k": source.kind, "b": body.bucket, "key": body.key},
                )
            ).scalar_one()
        )
        # The conversation's own messages (a 1:1 chat or group: its partner; an email: written to that person).
        await conn.execute(
            text(
                "update vanimo.l1_items set tone = :tone where source_kind = :k and bucket = :b and counterpart = :key"
            ),
            {"tone": effective, "k": source.kind, "b": body.bucket, "key": body.key},
        )
        await audit.record(conn, user, "persona.tone_changed", request_id=request.state.request_id)
    await rebuild(state.engine, state.vault, user, source.kind)
    return Response(status_code=204)


@router.put("/persona/settings", response_model=PersonaSettings)
async def put_persona_settings(
    body: PersonaSettings, user: CurrentUser, state: State, request: Request
) -> PersonaSettings:
    saved = await save_settings(state.engine, state.vault, user, body)
    async with user_tx(state.engine, user) as conn:
        await audit.record(conn, user, "persona.settings_saved", request_id=request.state.request_id)
    return saved


# --- sample workspace ---------------------------------------------------------------------------
class SamplePerson(BaseModel):
    name: str | None
    email: str


class SampleEmail(BaseModel):
    id: str
    conversationId: str
    subject: str | None
    sentAt: datetime
    sender: SamplePerson
    to: list[SamplePerson]
    cc: list[SamplePerson]
    direction: str
    body: str
    status: str  # learned | excluded | not_learned | received
    reasons: list[str]
    storedId: str | None


class SampleChatMessage(BaseModel):
    id: str
    sender: SamplePerson
    createdAt: datetime
    text: str
    fromMe: bool
    status: str
    storedId: str | None


class SampleChat(BaseModel):
    id: str
    chatType: str
    label: str
    members: list[SamplePerson]
    excluded: bool
    reasons: list[str]
    messages: list[SampleChatMessage]


class SampleMeeting(BaseModel):
    id: str
    subject: str | None
    start: datetime
    end: datetime
    organizer: SamplePerson | None
    attendees: list[SamplePerson]
    agenda: str | None
    excluded: bool
    reasons: list[str]


class SampleWorkspaceOut(BaseModel):
    note: str
    emails: list[SampleEmail]
    chats: list[SampleChat]
    meetings: list[SampleMeeting]


def _p(a: Any) -> SamplePerson:
    return SamplePerson(name=a.name, email=a.email)


def _why(decision: Any) -> list[str]:
    return sorted({r.kind for r in decision.reasons})


@router.get("/sample/workspace", response_model=SampleWorkspaceOut)
async def sample_workspace(
    user: CurrentUser, principal: CurrentPrincipal, source: UserSource, state: State
) -> SampleWorkspaceOut:
    from vanimo.controls.scan import CALENDAR_AHEAD, CALENDAR_BACK, chat_label, meeting_links
    from vanimo.sources.sample import SampleSource

    if not isinstance(source, SampleSource):
        raise HTTPException(404, detail={"error": "sample_workspace_only"})
    me = await self_email(source, principal.email)
    hasher = hasher_for(state.vault, user)
    async with user_tx(state.engine, user) as conn:
        ex = await load_engine(conn, state.vault, user, self_email=me, extra_org_domains=await source.org_domains())
        stored = {
            r.item_hash: str(r.id)
            for r in (
                await conn.execute(text("select id, item_hash from vanimo.l1_items where source_kind = 'sample'"))
            ).all()
        }
    headers = {h.id: h async for h in source.sent_headers()}
    emails = []
    for m in sorted(await source.all_messages(), key=lambda m: m.sent_at, reverse=True):
        status, reasons, stored_id = "received", [], None
        if m.direction == "sent":
            stored_id = stored.get(hasher("item", f"email:{m.id}"))
            decision = ex.message(headers[m.id]) if m.id in headers else None
            if stored_id:
                status = "learned"
            elif decision is not None and decision.excluded:
                status, reasons = "excluded", _why(decision)
            else:
                status = "not_learned"
        emails.append(
            SampleEmail(
                id=m.id,
                conversationId=m.conversation_id,
                subject=m.subject,
                sentAt=m.sent_at,
                sender=_p(m.sender),
                to=[_p(a) for a in m.to],
                cc=[_p(a) for a in m.cc],
                direction=m.direction,
                body=m.body,
                status=status,
                reasons=reasons,
                storedId=stored_id,
            )
        )
    now = datetime.now(UTC)
    by_url = meeting_links([e async for e in source.events(now - CALENDAR_BACK, now + CALENDAR_AHEAD)])
    chats = []
    async for c in source.chats():
        link = by_url.get(c.join_url or "")
        decision = ex.chat(
            c,
            meeting_hash=hasher("meeting", link[0]) if link else None,
            series_hash=hasher("series", link[1]) if link and link[1] else None,
        )
        msgs = []
        async for cm in source.chat_messages(c.id):
            sid = stored.get(hasher("item", f"chat:{c.id}:{cm.id}")) if cm.from_me else None
            st = (
                "received"
                if not cm.from_me
                else "learned"
                if sid
                else "excluded"
                if decision.excluded
                else "not_learned"
            )
            msgs.append(
                SampleChatMessage(
                    id=cm.id,
                    sender=_p(cm.sender),
                    createdAt=cm.created_at,
                    text=cm.text,
                    fromMe=cm.from_me,
                    status=st,
                    storedId=sid,
                )
            )
        others = [m for m in c.members if m.email.lower() != me]
        chats.append(
            SampleChat(
                id=c.id,
                chatType=c.chat_type,
                label=chat_label(c.topic, [m.name or m.email for m in others]),
                members=[_p(m) for m in c.members],
                excluded=decision.excluded,
                reasons=_why(decision),
                messages=sorted(msgs, key=lambda x: x.createdAt),
            )
        )
    meetings = []
    async for e in source.events(now - timedelta(days=60), now + timedelta(days=30)):
        decision = ex.meeting(e)
        meetings.append(
            SampleMeeting(
                id=e.id,
                subject=e.subject,
                start=e.start,
                end=e.end,
                organizer=_p(e.organizer) if e.organizer else None,
                attendees=[_p(a) for a in e.attendees],
                agenda=await source.event_agenda(e.id),
                excluded=decision.excluded,
                reasons=_why(decision),
            )
        )
    meetings.sort(key=lambda x: x.start, reverse=True)
    return SampleWorkspaceOut(
        note="Synthetic sample data, shown as Outlook and Teams would show it. Vanimo stores only the redacted "
        "copy of your own sent messages from allowed sources (open a learned item to see it).",
        emails=emails,
        chats=sorted(chats, key=lambda c: c.label.lower()),
        meetings=meetings,
    )
