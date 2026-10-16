"""Drafting endpoints (MVP plan M3): used by the Outlook add-in and the web app's Draft page.

* GET  /api/drafting/status   — which drafter runs (offline stand-in or Claude), quotas, readiness.
* GET  /api/drafting/threads  — recent conversations with received mail, headers only, each marked
                                if your rules or your organisation's exclude it (the thread picker).
* GET  /api/drafting/thread   — one conversation's last messages, for your own screen (gated).
* GET  /api/drafting/chats    — your recent Teams chats, roster metadata only (M5 chat picker).
* GET  /api/drafting/chat     — one chat's last messages, for your own screen (gated).
* POST /api/drafts            — draft a reply or a new email in your voice. Never sends.
* POST /api/drafts/check      — pre-send checks on the text you are about to send.
* GET  /api/drafts            — your recent drafts (metadata only, no text).
* POST /api/drafts/{id}/feedback — inserted, copied, opened as a reply or discarded; good or bad.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text

from vanimo import audit
from vanimo.api.deps import CurrentPrincipal, CurrentUser, State, UserSource
from vanimo.api.learning import self_email
from vanimo.controls.neversend import render_removed
from vanimo.controls.store import hasher_for, load_engine, load_matcher
from vanimo.db.session import user_tx
from vanimo.drafting.context import MAX_CHAT_MESSAGES, MAX_THREAD_MESSAGES, DraftError, _thread_headers, refusal
from vanimo.drafting.generate import OFFLINE_LABEL
from vanimo.drafting.service import (
    DraftInput,
    DraftResult,
    _chat_meeting,
    _sample_domains,
    check_text,
    create_draft,
    premium_used,
    require_review,
)
from vanimo.gates import onboarding_state
from vanimo.redaction.parse import strip_signature_noise
from vanimo.sources.base import Address, Chat

router = APIRouter(prefix="/api", tags=["drafting"])

_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}$")


class PersonIn(BaseModel):
    email: str = Field(max_length=320)
    name: str | None = Field(None, max_length=200)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL.match(v):
            raise ValueError("not an email address")
        return v

    def address(self) -> Address:
        return Address(email=self.email, name=self.name)


class PersonOut(BaseModel):
    email: str
    name: str | None


# --- status and thread picker --------------------------------------------------------------------
class StatusOut(BaseModel):
    generator: Literal["offline", "bedrock"]
    label: str
    defaultModel: str
    premiumModel: str
    premiumLeftToday: int
    reviewDone: bool
    learnedItems: int
    sourceKind: str


@router.get("/drafting/status", response_model=StatusOut)
async def drafting_status(user: CurrentUser, source: UserSource, state: State) -> StatusOut:
    async with user_tx(state.engine, user) as conn:
        onboarding, _ = await onboarding_state(conn, source.kind)
        used = await premium_used(conn)
        learned = (
            await conn.execute(text("select count(*) from vanimo.l1_items where source_kind = :k"), {"k": source.kind})
        ).scalar_one()
    s = state.settings
    return StatusOut(
        generator=s.drafter,
        label=OFFLINE_LABEL if s.drafter == "offline" else "Claude on Amazon Bedrock",
        defaultModel=s.model_default,
        premiumModel=s.model_premium,
        premiumLeftToday=max(0, s.premium_drafts_per_day - used),
        reviewDone=onboarding == "review_done",
        learnedItems=learned,
        sourceKind=source.kind,
    )


class ThreadItem(BaseModel):
    conversationId: str
    subject: str | None
    sender: PersonOut
    receivedAt: datetime
    excluded: bool
    excludedBy: Literal["you", "organisation", "unverifiable"] | None
    reasons: list[str]


@router.get("/drafting/threads", response_model=list[ThreadItem])
async def drafting_threads(
    user: CurrentUser, principal: CurrentPrincipal, source: UserSource, state: State
) -> list[ThreadItem]:
    """Headers only: no message text is read here."""
    me = await self_email(source, principal.email)
    async with user_tx(state.engine, user) as conn:
        ex = await load_engine(conn, state.vault, user, self_email=me, extra_org_domains=_sample_domains(source))
        matcher = await load_matcher(conn, state.vault, user)
    out = []
    for h in await source.recent_received(25):
        decision = ex.conversation(h.conversation_id, [h.sender, *h.to, *h.cc])
        out.append(
            ThreadItem(
                conversationId=h.conversation_id,
                subject=render_removed(matcher.mask(h.subject)[0]) if h.subject else None,
                sender=PersonOut(email=h.sender.email, name=h.sender.name),
                receivedAt=h.received_at,
                excluded=decision.excluded,
                excludedBy=refusal(decision).extra["by"] if decision.excluded else None,  # type: ignore[arg-type]
                reasons=sorted({r.kind for r in decision.reasons}),
            )
        )
    return out


class ThreadMessageOut(BaseModel):
    sender: PersonOut
    sentAt: datetime
    fromMe: bool
    text: str  # what Outlook shows you, with never-send words as [removed]


class ThreadOut(BaseModel):
    conversationId: str
    subject: str | None
    messages: list[ThreadMessageOut]
    participants: list[PersonOut]


@router.get("/drafting/thread", response_model=ThreadOut)
async def drafting_thread(
    user: CurrentUser,
    principal: CurrentPrincipal,
    source: UserSource,
    state: State,
    conversationId: str = Query(min_length=1, max_length=512),  # the client's name for it
) -> ThreadOut:
    """The last few messages of a conversation, for your own screen. Gated like drafting: the
    review must be done and the conversation allowed (metadata decides before text is read)."""
    await require_review(state, user, source)
    me = await self_email(source, principal.email)
    async with user_tx(state.engine, user) as conn:
        ex = await load_engine(conn, state.vault, user, self_email=me, extra_org_domains=_sample_domains(source))
        matcher = await load_matcher(conn, state.vault, user)
    headers = await _thread_headers(source, conversationId)
    if not headers:
        raise DraftError("thread_not_found", 404)
    conv = headers[0].conversation_id  # Graph's own form, as the rules use
    people = [a for h in headers for a in h.participants]
    decision = ex.conversation(conv, people)
    if decision.excluded:
        raise refusal(decision)
    messages = []
    subject = None
    for h in headers[-MAX_THREAD_MESSAGES:]:
        m = await source.message(h.id)
        if m is None:
            continue
        subject = m.subject or subject
        messages.append(
            ThreadMessageOut(
                sender=PersonOut(email=h.sender.email, name=h.sender.name),
                sentAt=h.sent_at,
                fromMe=h.sender.email.lower() == me,
                text=render_removed(matcher.mask(strip_signature_noise(m.body))[0]) or "",
            )
        )
    unique = {a.email.lower(): a for a in people if a.email}
    return ThreadOut(
        conversationId=conv,
        subject=render_removed(matcher.mask(subject)[0]) if subject else None,
        messages=messages,
        participants=[PersonOut(email=e, name=a.name) for e, a in unique.items()],
    )


# --- Teams chats (M5) -----------------------------------------------------------------------------
class ChatItem(BaseModel):
    chatId: str
    chatType: Literal["oneOnOne", "group", "meeting"]
    label: str  # the chat's name, or its members' names; never-send words as [removed]
    members: int
    lastActivityAt: datetime | None
    excluded: bool
    excludedBy: Literal["you", "organisation", "unverifiable"] | None
    reasons: list[str]


def chat_label(c: Chat, me: str) -> str:
    if c.topic:
        return c.topic
    names = [a.name or a.email for a in c.members if a.email.lower() != me]
    return ", ".join(names[:4]) + (f" +{len(names) - 4}" if len(names) > 4 else "") or "Chat"


MAX_CHAT_LIST = 200  # chats looked at (metadata) for the picker


@router.get("/drafting/chats", response_model=list[ChatItem])
async def drafting_chats(
    user: CurrentUser, principal: CurrentPrincipal, source: UserSource, state: State
) -> list[ChatItem]:
    """Rosters only: no message text is read here. Hidden chats aren't offered."""
    me = await self_email(source, principal.email)
    hasher = hasher_for(state.vault, user)
    async with user_tx(state.engine, user) as conn:
        ex = await load_engine(conn, state.vault, user, self_email=me, extra_org_domains=_sample_domains(source))
        matcher = await load_matcher(conn, state.vault, user)
        meetings = {
            r.key_hash: (r.meeting_hash, r.series_hash)
            for r in (
                await conn.execute(text("select key_hash, meeting_hash, series_hash from vanimo.source_chats"))
            ).all()
        }
    seen: list[Chat] = []
    async for c in source.chats():
        if not c.hidden:
            seen.append(c)
        if len(seen) >= MAX_CHAT_LIST:
            break
    seen.sort(key=lambda c: c.last_activity_at or datetime.min.replace(tzinfo=UTC), reverse=True)
    out = []
    for c in seen[:25]:
        meeting = meetings.get(hasher("chat", c.id))
        if c.chat_type == "meeting" and not (meeting and meeting[0]):
            excluded, by, reasons = True, "unverifiable", ["meeting_unknown"]
        else:
            decision = ex.chat(
                c, meeting_hash=meeting[0] if meeting else None, series_hash=meeting[1] if meeting else None
            )
            excluded = decision.excluded
            by = refusal(decision).extra["by"] if excluded else None
            reasons = sorted({r.kind for r in decision.reasons})
        out.append(
            ChatItem(
                chatId=c.id,
                chatType=c.chat_type,
                label=render_removed(matcher.mask(chat_label(c, me))[0]) or "Chat",
                members=len(c.members),
                lastActivityAt=c.last_activity_at,
                excluded=excluded,
                excludedBy=by,  # type: ignore[arg-type]
                reasons=reasons,
            )
        )
    return out


class ChatOut(BaseModel):
    chatId: str
    label: str
    messages: list[ThreadMessageOut]


@router.get("/drafting/chat", response_model=ChatOut)
async def drafting_chat(
    user: CurrentUser,
    principal: CurrentPrincipal,
    source: UserSource,
    state: State,
    chatId: str = Query(min_length=1, max_length=256),
) -> ChatOut:
    """A chat's last few messages, for your own screen: the review must be done and the roster allowed."""
    await require_review(state, user, source)
    me = await self_email(source, principal.email)
    hasher = hasher_for(state.vault, user)
    async with user_tx(state.engine, user) as conn:
        ex = await load_engine(conn, state.vault, user, self_email=me, extra_org_domains=_sample_domains(source))
        matcher = await load_matcher(conn, state.vault, user)
        meeting = await _chat_meeting(conn, hasher, chatId)
    chat = await source.chat(chatId)
    if chat is None:
        raise DraftError("chat_not_found", 404)
    if chat.chat_type == "meeting" and meeting is None:
        raise DraftError("conversation_excluded", 403, by="unverifiable", reasons=["meeting_unknown"])
    decision = ex.chat(chat, meeting_hash=meeting[0] if meeting else None, series_hash=meeting[1] if meeting else None)
    if decision.excluded:
        raise refusal(decision)
    chat_hash = hasher("chat", chat.id)
    msgs = sorted([m async for m in source.chat_messages(chat.id)], key=lambda m: m.created_at)
    shown = [
        ThreadMessageOut(
            sender=PersonOut(email=m.sender.email, name=m.sender.name),
            sentAt=m.created_at,
            fromMe=m.from_me,
            text=render_removed(matcher.mask(m.text)[0]) or "",
        )
        for m in msgs[-MAX_CHAT_MESSAGES:]
        if m.from_me or not ex.people_reasons([m.sender], chat_hash=chat_hash)
    ]
    return ChatOut(
        chatId=chat.id, label=render_removed(matcher.mask(chat_label(chat, me))[0]) or "Chat", messages=shown
    )


# --- drafts --------------------------------------------------------------------------------------
class DraftIn(BaseModel):
    mode: Literal["reply", "new"]
    surface: Literal["outlook", "web", "teams"] = "web"
    channel: Literal["email", "chat"] = "email"
    conversationId: str | None = Field(None, max_length=512)  # the chat ID for a Teams draft
    messageId: str | None = Field(None, max_length=512)  # Teams: the message being answered
    # The compose window's recipients (the add-in sends them). Omitted on a reply: the sender of the
    # last message (and, with replyAll, everyone else on it).
    to: list[PersonIn] | None = Field(None, max_length=50)
    cc: list[PersonIn] | None = Field(None, max_length=50)
    subject: str | None = Field(None, max_length=300)
    instruction: str | None = Field(None, max_length=1000)
    quality: Literal["auto", "standard", "premium"] = "auto"
    replyAll: bool = False
    # Draft once, in memory, in a conversation you excluded (never in one your organisation excluded).
    oneOff: bool = False


class CheckOut(BaseModel):
    code: str
    severity: Literal["block", "warn", "info"]
    message: str


class AudienceOut(BaseModel):
    relationship: str
    label: str
    to: list[PersonOut]
    cc: list[PersonOut]
    internal: int
    external: int


class TimingOut(BaseModel):
    totalMs: float
    modelMs: float | None


class DraftOut(BaseModel):
    id: str | None  # None for a one-off draft (never stored)
    text: str
    generator: Literal["offline", "bedrock"]
    label: str
    modelId: str  # the model used, or the one Claude would use (offline stand-in)
    tier: Literal["default", "premium"]
    routeReason: str
    audience: AudienceOut
    styleSlice: str | None
    learned: bool
    basedOn: int  # messages behind the style card used
    exemplars: int
    checks: list[CheckOut]
    insertAllowed: bool  # False while a "block" check stands: the user must confirm first
    oneOff: bool
    timing: TimingOut
    channel: Literal["email", "chat"] = "email"
    chatUsers: list[str] = Field(default_factory=list)  # Teams: who "Open chat" opens it with


def _people(rs: list) -> list[PersonOut]:  # type: ignore[type-arg]
    return [PersonOut(email=r.address.email, name=r.address.name) for r in rs]


@router.post("/drafts", response_model=DraftOut)
async def post_draft(
    body: DraftIn, user: CurrentUser, principal: CurrentPrincipal, source: UserSource, state: State, request: Request
) -> DraftOut:
    me = await self_email(source, principal.email)
    req = DraftInput(
        mode=body.mode,
        surface=body.surface,
        conversation_id=body.conversationId,
        to=[p.address() for p in body.to] if body.to is not None else None,
        cc=[p.address() for p in body.cc] if body.cc is not None else None,
        subject=body.subject,
        instruction=body.instruction,
        quality=body.quality,
        reply_all=body.replyAll,
        one_off=body.oneOff,
        channel=body.channel,
        message_id=body.messageId,
    )
    result = await create_draft(state, user, source, self_email=me, req=req, request_id=request.state.request_id)
    return draft_out(result)


def draft_out(result: DraftResult) -> DraftOut:
    a = result.audience
    return DraftOut(
        id=result.id,
        text=result.text,
        generator=result.generator,  # type: ignore[arg-type]
        label=result.label,
        modelId=result.model_id,
        tier=result.tier,  # type: ignore[arg-type]
        routeReason=result.route_reason,
        audience=AudienceOut(
            relationship=a.relationship,
            label=a.label,
            to=_people(a.to),
            cc=_people(a.cc),
            internal=a.internal,
            external=a.external,
        ),
        styleSlice=result.card_key,
        learned=result.learned,
        basedOn=result.based_on,
        exemplars=result.exemplars,
        checks=[CheckOut(code=c.code, severity=c.severity, message=c.message) for c in result.checks],
        insertAllowed=result.insert_allowed,
        oneOff=result.one_off,
        timing=TimingOut(totalMs=result.total_ms, modelMs=result.model_ms),
        channel=result.channel,  # type: ignore[arg-type]
        chatUsers=result.chat_users,
    )


class CheckIn(BaseModel):
    body: str = Field(max_length=500_000)  # the quoted thread is cut off server-side
    to: list[PersonIn] = Field(default_factory=list, max_length=100)
    cc: list[PersonIn] = Field(default_factory=list, max_length=100)
    conversationId: str | None = Field(None, max_length=512)


class ChecksOut(BaseModel):
    checks: list[CheckOut]
    insertAllowed: bool


@router.post("/drafts/check", response_model=ChecksOut)
async def post_check(
    body: CheckIn, user: CurrentUser, principal: CurrentPrincipal, source: UserSource, state: State
) -> ChecksOut:
    """Your text is checked in memory and forgotten: nothing is stored or logged."""
    me = await self_email(source, principal.email)
    found = await check_text(
        state,
        user,
        source,
        self_email=me,
        body=body.body,
        to=[p.address() for p in body.to],
        cc=[p.address() for p in body.cc],
        conversation_id=body.conversationId,
    )
    return ChecksOut(
        checks=[CheckOut(code=c.code, severity=c.severity, message=c.message) for c in found],
        insertAllowed=not any(c.severity == "block" for c in found),
    )


class DraftSummary(BaseModel):
    id: str
    createdAt: datetime
    surface: str
    mode: str
    generator: str
    tier: str
    modelId: str | None
    relationship: str
    wordCount: int
    latencyMs: int | None
    checks: list[str]
    outcome: str | None
    rating: str | None


@router.get("/drafts", response_model=list[DraftSummary])
async def list_drafts(user: CurrentUser, source: UserSource, state: State) -> list[DraftSummary]:
    async with user_tx(state.engine, user) as conn:
        rows = (
            await conn.execute(
                text(
                    "select id, created_at, surface, mode, generator, tier, model_id, relationship, word_count, "
                    "latency_ms, checks, outcome, rating from vanimo.drafts where source_kind = :k "
                    "order by created_at desc limit 20"
                ),
                {"k": source.kind},
            )
        ).all()
    return [
        DraftSummary(
            id=str(r.id),
            createdAt=r.created_at,
            surface=r.surface,
            mode=r.mode,
            generator=r.generator,
            tier=r.tier,
            modelId=r.model_id,
            relationship=r.relationship,
            wordCount=r.word_count,
            latencyMs=r.latency_ms,
            checks=[c["code"] for c in r.checks],
            outcome=r.outcome,
            rating=r.rating,
        )
        for r in rows
    ]


class FeedbackIn(BaseModel):
    outcome: Literal["inserted", "copied", "opened_reply", "opened_chat", "discarded"] | None = None
    rating: Literal["good", "bad"] | None = None


@router.post("/drafts/{draft_id}/feedback", status_code=204)
async def draft_feedback(
    draft_id: uuid.UUID, body: FeedbackIn, user: CurrentUser, state: State, request: Request
) -> Response:
    async with user_tx(state.engine, user) as conn:
        row = (
            await conn.execute(
                text(
                    "update vanimo.drafts set outcome = coalesce(:o, outcome), rating = coalesce(:r, rating), "
                    "outcome_at = now() where id = :id returning id"
                ),
                {"o": body.outcome, "r": body.rating, "id": draft_id},
            )
        ).first()
        if row is None:
            raise DraftError("not_found", 404)
        await audit.record(
            conn,
            user,
            "draft.feedback",
            target_kind="draft",
            target_ref=str(draft_id),
            request_id=request.state.request_id,
        )
    return Response(status_code=204)
