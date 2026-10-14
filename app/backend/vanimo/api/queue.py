"""Drafts queue and drafts in the Outlook Drafts folder (MVP plan M4).

* GET  /api/queue                   — conversations waiting for your reply, with any Vanimo draft.
* POST /api/queue/prepare           — draft a reply now (and put it in Outlook if you opted in).
* POST /api/queue/dismiss           — "no reply needed".
* POST /api/queue/tidy              — remove unused placed drafts (unsent and untouched only).
* POST /api/drafts/{id}/place       — put a draft (as on your screen) in your Drafts folder.
* GET/PUT /api/drafting/settings    — your opt-in to drafts in the Drafts folder.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from vanimo.api.deps import CurrentPrincipal, CurrentUser, State, UserSource
from vanimo.api.drafting import DraftOut, PersonOut, draft_out
from vanimo.api.learning import self_email
from vanimo.db.session import user_tx
from vanimo.drafting import queue as q
from vanimo.drafting.checks import blocked
from vanimo.drafting.service import DraftInput, create_draft

router = APIRouter(prefix="/api", tags=["queue"])


class SettingsOut(BaseModel):
    outlookDrafts: bool
    staleDays: int
    allowedByOrganisation: bool


def _settings(s: q.Settings) -> SettingsOut:
    return SettingsOut(
        outlookDrafts=s.outlook_drafts, staleDays=s.stale_days, allowedByOrganisation=s.allowed_by_organisation
    )


@router.get("/drafting/settings", response_model=SettingsOut)
async def get_settings(user: CurrentUser, state: State) -> SettingsOut:
    async with user_tx(state.engine, user) as conn:
        return _settings(await q.load_settings(conn))


class SettingsIn(BaseModel):
    outlookDrafts: bool
    staleDays: int = Field(3, ge=1, le=14)


@router.put("/drafting/settings", response_model=SettingsOut)
async def put_settings(body: SettingsIn, user: CurrentUser, state: State) -> SettingsOut:
    return _settings(await q.save_settings(state, user, outlook_drafts=body.outlookDrafts, stale_days=body.staleDays))


class QueueDraft(BaseModel):
    id: str
    createdAt: datetime
    placed: bool
    placedState: str | None
    webLink: str | None
    outcome: str | None
    matchState: str
    blocked: bool


class QueueItemOut(BaseModel):
    conversationId: str
    subject: str | None
    sender: PersonOut
    receivedAt: datetime
    needsReply: bool
    reason: str
    excluded: bool
    excludedBy: str | None
    ccOnly: bool
    draft: QueueDraft | None


class QueueOut(BaseModel):
    items: list[QueueItemOut]
    settings: SettingsOut
    sourceKind: str


@router.get("/queue", response_model=QueueOut)
async def get_queue(user: CurrentUser, principal: CurrentPrincipal, source: UserSource, state: State) -> QueueOut:
    me = await self_email(source, principal.email)
    items = await q.waiting(state, user, source, self_email=me)
    async with user_tx(state.engine, user) as conn:
        settings = await q.load_settings(conn)
    return QueueOut(
        items=[
            QueueItemOut(
                conversationId=i.conversation_id,
                subject=i.subject,
                sender=PersonOut(email=i.sender.email, name=i.sender.name),
                receivedAt=i.received_at,
                needsReply=i.needs_reply,
                reason=i.reason,
                excluded=i.excluded,
                excludedBy=i.excluded_by,
                ccOnly=i.cc_only,
                draft=QueueDraft(**i.draft) if i.draft else None,
            )
            for i in items
        ],
        settings=_settings(settings),
        sourceKind=source.kind,
    )


class PrepareIn(BaseModel):
    conversationId: str = Field(min_length=1, max_length=512)
    instruction: str | None = Field(None, max_length=1000)


class PrepareOut(BaseModel):
    draft: DraftOut
    placed: bool
    webLink: str | None
    notPlacedReason: Literal["off", "organisation_off", "blocked", "not_saved"] | None


@router.post("/queue/prepare", response_model=PrepareOut)
async def prepare(
    body: PrepareIn, user: CurrentUser, principal: CurrentPrincipal, source: UserSource, state: State, request: Request
) -> PrepareOut:
    """Draft a reply now; with your opt-in, it also goes to your Drafts folder (never one with a
    blocking check: those need your confirmation on screen first)."""
    me = await self_email(source, principal.email)
    result = await create_draft(
        state,
        user,
        source,
        self_email=me,
        req=DraftInput(
            mode="reply", surface="queue", conversation_id=body.conversationId, instruction=body.instruction
        ),
        request_id=request.state.request_id,
    )
    async with user_tx(state.engine, user) as conn:
        settings = await q.load_settings(conn)
    reason: Any = None
    placed: dict[str, Any] = {"placed": False, "webLink": None}
    if not settings.outlook_drafts:
        reason = "off"
    elif not settings.allowed_by_organisation:
        reason = "organisation_off"
    elif blocked(result.checks):
        reason = "blocked"
    elif result.id is None:
        reason = "not_saved"
    else:
        placed = await q.place(
            state, user, source, draft_id=result.id, text_shown=result.text, request_id=request.state.request_id
        )
    return PrepareOut(
        draft=draft_out(result), placed=placed["placed"], webLink=placed["webLink"], notPlacedReason=reason
    )


class ConversationIn(BaseModel):
    conversationId: str = Field(min_length=1, max_length=512)


@router.post("/queue/dismiss", status_code=204)
async def dismiss(body: ConversationIn, user: CurrentUser, state: State) -> None:
    await q.dismiss(state, user, body.conversationId)


@router.post("/queue/tidy")
async def tidy(user: CurrentUser, source: UserSource, state: State) -> dict[str, int]:
    return await q.tidy(state, user, source)


class PlaceIn(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)  # as on your screen, possibly edited
    confirmed: bool = False  # you checked a blocking warning another way


class PlaceOut(BaseModel):
    placed: bool
    webLink: str | None


@router.post("/drafts/{draft_id}/place", response_model=PlaceOut)
async def place_draft(
    draft_id: uuid.UUID, body: PlaceIn, user: CurrentUser, source: UserSource, state: State, request: Request
) -> PlaceOut:
    out = await q.place(
        state,
        user,
        source,
        draft_id=str(draft_id),
        text_shown=body.text,
        confirmed=body.confirmed,
        request_id=request.state.request_id,
    )
    return PlaceOut(placed=out["placed"], webLink=out["webLink"])
