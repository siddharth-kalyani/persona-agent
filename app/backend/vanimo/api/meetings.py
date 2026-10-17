"""Meeting memory endpoints (MVP plan M6): your Teams meetings, what they decided and asked for, and
questions about them answered with citations.

* GET    /api/meetings                   — the meetings Vanimo remembers (re-checked against your rules)
* POST   /api/meetings/scan              — read the transcripts of meetings that ended since the last look
* GET    /api/meetings/{id}              — one meeting: its notes, and its transcript while it's kept (30 days)
* POST   /api/meetings/ask               — a question about your meetings → an answer with citations
* PUT    /api/meetings/notes/{id}        — "not right" (hide a note) or restore it
* PUT    /api/meetings/{id}/speakers     — "this wasn't Lisa": move a speaker's words to someone else
* DELETE /api/meetings/{id}              — forget a meeting (and never read it again)
* GET    /api/admin/meetings/health      — the admin's transcript health checks

Everything shown is rendered for its owner only: names back from tokens, never-send words as
[removed] (as they are now), and nothing from a meeting a rule excludes, even before the purge job.
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from vanimo import audit
from vanimo.api.deps import AdminPrincipal, CurrentPrincipal, CurrentUser, State, UserSource
from vanimo.api.learning import self_email
from vanimo.commitments import store as ledger
from vanimo.commitments.extract import Found
from vanimo.controls.neversend import Matcher, render_removed
from vanimo.controls.store import hasher_for, load_engine, load_matcher, lock_user_controls
from vanimo.db.session import UserRef, user_tx
from vanimo.drafting.context import DraftError, DraftThrottle, build_redactor
from vanimo.drafting.service import _known, _sample_domains
from vanimo.memory import ask as asking
from vanimo.memory import ingest
from vanimo.memory.atoms import OFFLINE_LABEL
from vanimo.redaction.marks import TOKEN
from vanimo.redaction.pipeline import RedactionBlocked, rehydrate
from vanimo.sources.base import TranscriptsUnavailable
from vanimo.vault import Vault

router = APIRouter(prefix="/api/meetings", tags=["meetings"])
admin_router = APIRouter(prefix="/api/admin/meetings", tags=["meetings"])

ASK_THROTTLE = DraftThrottle()
ASKS_PER_MINUTE = 10
ASKS_PER_DAY = 300
Kind = Literal["decision", "action_item", "commitment", "requirement", "open_question", "risk", "idea"]
Side = Literal["me", "internal", "external", "unknown"]


# --- rendering for the owner ----------------------------------------------------------------
class Display:
    """Names back from tokens (any stored form of a person's name), never-send words masked live."""

    def __init__(self, tokens: dict[str, str], matcher: Matcher) -> None:
        self.matcher = matcher
        self.tokens = dict(tokens)
        by_stem: dict[str, str] = {}
        for tok, value in tokens.items():
            stem = asking._stem(tok)
            if tok.endswith(".full⟧") or stem not in by_stem:
                by_stem[stem] = value
        self._by_stem = by_stem

    def name(self, token: str | None) -> str:
        if not token:
            return "Someone"
        if token.startswith("⟦ME"):
            return "You"
        value = self.tokens.get(token) or self._by_stem.get(asking._stem(token))
        return render_removed(self.matcher.mask(value)[0]) or "Someone" if value else "Someone"

    def show(self, l1: str | None) -> str:
        if not l1:
            return ""
        filled = TOKEN.sub(
            lambda m: self.tokens.get(m.group()) or self._by_stem.get(asking._stem(m.group())) or m.group(), l1
        )
        return render_removed(self.matcher.mask(rehydrate(filled, {}))[0]) or ""


async def _display(conn: AsyncConnection, vault: Vault, user: UserRef) -> Display:
    t, u = user.tenant_id, user.user_id
    tokens = {
        r.token: vault.decrypt_user(t, u, r.value_enc, "l1_token") or ""
        for r in (await conn.execute(text("select token, value_enc from vanimo.l1_tokens"))).all()
    }
    return Display(tokens, await load_matcher(conn, vault, user))


def _excluded(row: Any, engine: Any) -> bool:
    return engine.lineage(
        [(p["p"], list(p["d"])) for p in row.people], meeting_hash=row.meeting_hash, series_hash=row.series_hash
    ).excluded


# --- list -------------------------------------------------------------------------------------
class EpisodeOut(BaseModel):
    id: str
    title: str
    startsAt: datetime
    endsAt: datetime
    external: bool  # people from outside the organisation were invited
    organizedByMe: bool
    attribution: Literal["named", "unattributed"]
    notes: dict[str, int]  # active notes by kind
    transcriptUntil: datetime | None  # the transcript (L1) is kept until then, for citations
    extractor: Literal["offline", "bedrock"]


class MeetingsOut(BaseModel):
    items: list[EpisodeOut]
    on: bool  # the organisation's switch
    label: str
    hidden: int  # stored but excluded by a rule added since (the purge job removes them)


async def _episode_rows(conn: AsyncConnection, source_kind: str, episode_id: uuid.UUID | None = None) -> list[Any]:
    where, params = "source_kind = :k", {"k": source_kind}
    if episode_id is not None:
        where, params = "source_kind = :k and id = :id", {"k": source_kind, "id": episode_id}
    return list(
        (
            await conn.execute(
                text(
                    "select id, title_enc, starts_at, ends_at, transcript_at, people, roster, meeting_hash, "  # noqa: S608
                    "series_hash, external, organizer_is_me, attribution, segments_until, extractor "
                    f"from vanimo.episodes where {where} order by starts_at desc limit 300"
                ),
                params,
            )
        ).all()
    )


def _label(state: Any) -> str:
    return OFFLINE_LABEL if state.settings.drafter == "offline" else "Claude on Amazon Bedrock"


@router.get("", response_model=MeetingsOut)
async def list_meetings(
    user: CurrentUser, principal: CurrentPrincipal, source: UserSource, state: State
) -> MeetingsOut:
    me = await self_email(source, principal.email)
    v, t, u = state.vault, user.tenant_id, user.user_id
    async with user_tx(state.engine, user) as conn:
        on = await ingest.meeting_memory_on(conn)
        engine = await load_engine(conn, v, user, self_email=me, extra_org_domains=_sample_domains(source))
        rows = await _episode_rows(conn, source.kind) if on else []
        counts = (
            await conn.execute(
                text(
                    "select episode_id, kind, count(*) as n from vanimo.memory_atoms where status = 'active' "
                    "group by episode_id, kind"
                )
            )
        ).all()
        display = await _display(conn, v, user)
    by_ep: dict[str, dict[str, int]] = {}
    for c in counts:
        by_ep.setdefault(str(c.episode_id), {})[c.kind] = c.n
    now = datetime.now(UTC)
    live = [r for r in rows if not _excluded(r, engine)]
    return MeetingsOut(
        items=[_episode_out(r, display, v, t, u, by_ep.get(str(r.id), {}), now) for r in live],
        on=on,
        label=_label(state),
        hidden=len(rows) - len(live),
    )


def _episode_out(
    r: Any, display: Display, v: Vault, t: Any, u: Any, notes: dict[str, int], now: datetime
) -> EpisodeOut:
    return EpisodeOut(
        id=str(r.id),
        title=display.show(v.decrypt_user(t, u, r.title_enc, "episode_title")) or "(no subject)",
        startsAt=r.starts_at,
        endsAt=r.ends_at,
        external=r.external,
        organizedByMe=r.organizer_is_me,
        attribution=r.attribution,
        notes=notes,
        transcriptUntil=r.segments_until if r.segments_until > now else None,
        extractor=r.extractor,
    )


# --- scan -------------------------------------------------------------------------------------
class ScanOut(BaseModel):
    stored: int
    atoms: int
    promises: int
    excluded: int
    waiting: int
    pending: bool
    skipped: bool
    off: bool
    unavailable: str | None
    leftOut: int  # turns left out: a speaker not on the invite, or text that couldn't be redacted


@router.post("/scan", response_model=ScanOut)
async def scan_meetings(user: CurrentUser, principal: CurrentPrincipal, source: UserSource, state: State) -> ScanOut:
    me = await self_email(source, principal.email)
    result = await ingest.scan(state, user, source, self_email=me)
    return ScanOut(**ingest.summary(result))


# --- one meeting -------------------------------------------------------------------------------
class NoteOut(BaseModel):
    id: str
    kind: Kind
    text: str
    quote: str
    speaker: str
    speakerId: str | None  # an opaque ID for speaker corrections
    speakerSide: Side
    owner: str | None
    saidAt: datetime
    dueAt: datetime | None
    duePhrase: str | None
    trust: Literal["high", "medium", "low"]
    status: Literal["active", "dismissed"]
    turn: int


class TurnOut(BaseModel):
    turn: int
    at: datetime
    speaker: str
    speakerId: str | None
    speakerSide: Side
    text: str


class PersonOut(BaseModel):
    id: str
    name: str
    side: Side


class EpisodeDetail(EpisodeOut):
    notesList: list[NoteOut]
    transcript: list[TurnOut]
    people: list[PersonOut]


async def _live_episode(
    conn: AsyncConnection, state: Any, user: UserRef, source: Any, me: str, episode_id: uuid.UUID
) -> Any:
    rows = await _episode_rows(conn, source.kind, episode_id)
    if not rows or not await ingest.meeting_memory_on(conn):
        raise DraftError("not_found", 404)
    engine = await load_engine(conn, state.vault, user, self_email=me, extra_org_domains=_sample_domains(source))
    if _excluded(rows[0], engine):
        raise DraftError("not_found", 404)
    return rows[0]


@router.get("/{episode_id}", response_model=EpisodeDetail)
async def get_meeting(
    episode_id: uuid.UUID, user: CurrentUser, principal: CurrentPrincipal, source: UserSource, state: State
) -> EpisodeDetail:
    me = await self_email(source, principal.email)
    v, t, u = state.vault, user.tenant_id, user.user_id
    async with user_tx(state.engine, user) as conn:
        r = await _live_episode(conn, state, user, source, me, episode_id)
        atoms = (
            await conn.execute(
                text(
                    "select id, kind, text_enc, quote_enc, speaker, speaker_side, owner, said_at, due_at, "
                    "due_phrase_enc, trust, status, seg_from from vanimo.memory_atoms where episode_id = :id "
                    "order by said_at, kind"
                ),
                {"id": episode_id},
            )
        ).all()
        segs = (
            await conn.execute(
                text(
                    "select ordinal, starts_ms, speaker, speaker_side, text_enc from vanimo.episode_segments "
                    "where episode_id = :id and expires_at > now() order by ordinal"
                ),
                {"id": episode_id},
            )
        ).all()
        display = await _display(conn, v, user)
    now = datetime.now(UTC)
    active = Counter(a.kind for a in atoms if a.status == "active")
    base = _episode_out(r, display, v, t, u, dict(active), now)
    return EpisodeDetail(
        **base.model_dump(),
        notesList=[
            NoteOut(
                id=str(a.id),
                kind=a.kind,
                text=display.show(v.decrypt_user(t, u, a.text_enc, "atom_text")),
                quote=display.show(v.decrypt_user(t, u, a.quote_enc, "atom_quote")),
                speaker=display.name(a.speaker) if a.speaker else "Someone (no speaker names)",
                speakerId=a.speaker,
                speakerSide=a.speaker_side,
                owner=display.name(a.owner) if a.owner else None,
                saidAt=a.said_at,
                dueAt=a.due_at,
                duePhrase=display.show(p) or None
                if (p := v.decrypt_user(t, u, a.due_phrase_enc, "atom_due"))
                else None,
                trust=a.trust,
                status=a.status,
                turn=a.seg_from,
            )
            for a in atoms
        ],
        transcript=[
            TurnOut(
                turn=s.ordinal,
                at=r.transcript_at + timedelta(milliseconds=max(s.starts_ms, 0)),
                speaker=display.name(s.speaker) if s.speaker else "Someone",
                speakerId=s.speaker,
                speakerSide=s.speaker_side,
                text=display.show(v.decrypt_user(t, u, s.text_enc, "segment_text")),
            )
            for s in segs
        ],
        people=[PersonOut(id=p["t"], name=display.name(p["t"]), side=p["s"]) for p in r.roster],
    )


class NoteIn(BaseModel):
    action: Literal["dismiss", "restore"]


@router.put("/notes/{note_id}", status_code=204)
async def decide_note(note_id: uuid.UUID, body: NoteIn, user: CurrentUser, state: State, request: Request) -> Response:
    status = "dismissed" if body.action == "dismiss" else "active"
    async with user_tx(state.engine, user) as conn:
        row = (
            await conn.execute(
                text(
                    "update vanimo.memory_atoms set status = :s, status_at = case when :s = 'active' then null "
                    "else now() end where id = :id returning id"
                ),
                {"s": status, "id": note_id},
            )
        ).first()
        if row is None:
            raise DraftError("not_found", 404)
        await audit.record(conn, user, f"meeting_note.{body.action}", target_kind="memory_atom",
                           target_ref=str(note_id), request_id=request.state.request_id)  # fmt: skip
    return Response(status_code=204)


class SpeakerIn(BaseModel):
    fromId: str = Field(max_length=40)
    toId: str | None = Field(None, max_length=40)  # None: "I don't know who this was"


@router.put("/{episode_id}/speakers", status_code=204)
async def correct_speaker(
    episode_id: uuid.UUID,
    body: SpeakerIn,
    user: CurrentUser,
    principal: CurrentPrincipal,
    source: UserSource,
    state: State,
    request: Request,
) -> Response:
    """Teams attributes speech by display name; when it got someone wrong, the user moves that
    speaker's words (turns and notes) to another person in the meeting, or to nobody. Promises follow:
    words moved to you add your promises to the ledger; words moved away remove the open ones."""
    me = await self_email(source, principal.email)
    async with user_tx(state.engine, user) as conn:
        await lock_user_controls(conn, user)
        r = await _live_episode(conn, state, user, source, me, episode_id)
        roster = {p["t"]: p["s"] for p in r.roster}
        if body.fromId not in roster or (body.toId is not None and body.toId not in roster) or body.fromId == body.toId:
            raise DraftError("unknown_speaker", 422)
        to_side = roster[body.toId] if body.toId else "unknown"
        moved = (
            await conn.execute(
                text(
                    "select id, quote_enc, text_enc, due_at, due_phrase_enc, said_at from vanimo.memory_atoms "
                    "where episode_id = :id and speaker = :f and kind = 'commitment'"
                ),
                {"id": episode_id, "f": body.fromId},
            )
        ).all()
        for table in ("episode_segments", "memory_atoms"):
            await conn.execute(
                text(
                    f"update vanimo.{table} set speaker = :to, speaker_side = :side "  # noqa: S608 - fixed names
                    "where episode_id = :id and speaker = :f"
                ),
                {"to": body.toId, "side": to_side, "id": episode_id, "f": body.fromId},
            )
        await conn.execute(
            text(
                "update vanimo.memory_atoms set owner = :to where episode_id = :id and kind = 'commitment' "
                "and owner = :f"
            ),
            {"to": body.toId, "id": episode_id, "f": body.fromId},
        )
        from_me = roster[body.fromId] == "me"
        await _move_promises(conn, state, user, source.kind, r, moved, from_me=from_me, to_me=to_side == "me")
        await audit.record(conn, user, "meeting.speaker_corrected", target_kind="episode", target_ref=str(episode_id),
                           request_id=request.state.request_id)  # fmt: skip
    return Response(status_code=204)


async def _move_promises(
    conn: AsyncConnection, state: Any, user: UserRef, source_kind: str, ep: Any, atoms: list[Any], *, from_me: bool,
    to_me: bool,
) -> None:  # fmt: skip
    if from_me == to_me or not atoms:
        return
    v, t, u = state.vault, user.tenant_id, user.user_id
    item = ingest.meeting_item(hasher_for(v, user), ep.meeting_hash)
    if from_me:
        hashes = [
            ledger.promise_hash(v, user, item, v.decrypt_user(t, u, a.quote_enc, "atom_quote") or "") for a in atoms
        ]
        await conn.execute(
            text(
                "delete from vanimo.commitments where channel = 'meeting' and meeting_hash = :mh and status = 'open' "
                "and promise_hash = any(:h)"
            ),
            {"mh": ep.meeting_hash, "h": hashes},
        )
        return
    unit = ledger.Unit(
        channel="meeting", item_hash=item, thread_hash=ep.meeting_hash,
        people=[(p["p"], list(p["d"])) for p in ep.people],
        relationship="external" if ep.external else "peer", sent_at=ep.starts_at, text="", tokens={}, ref=None,
        meeting_hash=ep.meeting_hash, series_hash=ep.series_hash,
    )  # fmt: skip
    cands = []
    for n, a in enumerate(atoms):
        quote = v.decrypt_user(t, u, a.quote_enc, "atom_quote") or ""
        what = v.decrypt_user(t, u, a.text_enc, "atom_text") or ""
        phrase = v.decrypt_user(t, u, a.due_phrase_enc, "atom_due")
        cands.append(ledger.Candidate(ledger.Unit(**{**unit.__dict__, "sent_at": a.said_at}), n,
                                      Found(quote, what, phrase, a.due_at)))  # fmt: skip
    matcher = await load_matcher(conn, v, user)
    await ledger.insert(conn, v, user, source_kind, cands, matcher, extractor="offline")


@router.delete("/{episode_id}", status_code=204)
async def forget_meeting(
    episode_id: uuid.UUID, user: CurrentUser, source: UserSource, state: State, request: Request
) -> Response:
    """Forget a meeting: its notes, its transcript and the promises it added; it's never read again."""
    async with user_tx(state.engine, user) as conn:
        await lock_user_controls(conn, user)
        row = (
            await conn.execute(
                text("delete from vanimo.episodes where id = :id and source_kind = :k returning meeting_hash, ends_at"),
                {"id": episode_id, "k": source.kind},
            )
        ).first()
        if row is None:
            raise DraftError("not_found", 404)
        await conn.execute(
            text("delete from vanimo.commitments where channel = 'meeting' and meeting_hash = :mh"),
            {"mh": row.meeting_hash},
        )
        await ingest._record(conn, user, source.kind, row.meeting_hash, "deleted", "by_user", row.ends_at)
        from vanimo.controls.jobs import gc_tokens

        await gc_tokens(conn, state.vault, user)
        await audit.record(conn, user, "meeting.forgotten", target_kind="episode", target_ref=str(episode_id),
                           request_id=request.state.request_id)  # fmt: skip
    return Response(status_code=204)


# --- questions -----------------------------------------------------------------------------------
class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=300)
    meetingId: uuid.UUID | None = None  # the meeting the user picked when asked "which one?"


class CitationOut(BaseModel):
    n: int
    meetingId: str
    title: str
    meetingStart: datetime
    kind: str
    noteId: str | None
    at: datetime
    endAt: datetime
    speaker: str
    quote: str
    turn: int


class MeetingRefOut(BaseModel):
    id: str
    title: str
    startsAt: datetime


class AnswerOut(BaseModel):
    answer: str
    citations: list[CitationOut]
    abstained: bool
    clarify: bool  # two meetings match: pick one (`candidates`) and ask again
    candidates: list[MeetingRefOut]
    when: str  # how the question's time was understood ("Tuesday at 16:00"), or ""
    label: str


@router.post("/ask", response_model=AnswerOut)
async def ask_meetings(
    body: AskIn, user: CurrentUser, principal: CurrentPrincipal, source: UserSource, state: State, request: Request
) -> AnswerOut:
    try:
        ASK_THROTTLE.check(f"ask:{user.user_id}", per_minute=ASKS_PER_MINUTE, per_day=ASKS_PER_DAY)
    except DraftError as exc:
        raise DraftError("too_many_questions", 429) from exc
    me = await self_email(source, principal.email)
    v = state.vault
    tz = state.settings.cell_config.zone
    async with user_tx(state.engine, user) as conn:
        if not await ingest.meeting_memory_on(conn):
            raise DraftError("meeting_memory_off", 403)
        engine = await load_engine(conn, v, user, self_email=me, extra_org_domains=_sample_domains(source))
        names = await asking._names(conn, v, user)
        query = asking.parse_question(body.question, datetime.now(UTC), tz, names)
        evidence, ambiguous, candidates, _ = await asking.gather(
            conn, v, user, query, tz, source_kind=source.kind, live=lambda r: not _excluded(r, engine),
            episode_id=str(body.meetingId) if body.meetingId else None,
        )  # fmt: skip
        display = await _display(conn, v, user)
        _, known_people = await _known(conn, state, user)
        await audit.record(conn, user, "meeting.ask", request_id=request.state.request_id)
    refs = [MeetingRefOut(id=c.id, title=display.show(c.title), startsAt=c.starts_at) for c in candidates]
    if ambiguous:
        return AnswerOut(answer="More than one meeting matches. Which one did you mean?", citations=[], abstained=True,
                         clarify=True, candidates=refs, when=query.when.label, label=_label(state))  # fmt: skip
    if not evidence:
        where = f" ({query.when.label})" if query.when.label else ""
        text_ = f"I couldn't find that in your meeting notes{where}."
        if refs:
            text_ += " These meetings are close; you can ask about one of them."
        return AnswerOut(answer=text_, citations=[], abstained=True, clarify=False, candidates=refs,
                         when=query.when.label, label=_label(state))  # fmt: skip
    # The question goes to the model as L1, like any other text (names become the same tokens).
    llm = router_ = None
    question_l1 = ""
    if state.settings.drafter == "bedrock":
        directory = await state.directory_cache.get((str(user.user_id), source.kind), source, me)
        async with user_tx(state.engine, user) as conn:
            matcher = await load_matcher(conn, v, user)
        try:
            question_l1 = (
                build_redactor(matcher, hasher_for(v, user), directory, [], known_people).redact(body.question).text
            )
            llm, router_ = state.llm, state.router
        except RedactionBlocked:
            llm = None
    answer, _ = await asking.compose(llm, router_, question_l1, evidence, tz, display.name)
    return AnswerOut(
        answer=display.show(answer),
        citations=[
            CitationOut(
                n=e.n,
                meetingId=e.episode_id,
                title=display.show(e.title),
                meetingStart=e.episode_start,
                kind=e.kind,
                noteId=e.atom_id,
                at=e.at,
                endAt=e.end_at,
                speaker=display.name(e.speaker) if e.speaker else "Someone",
                quote=display.show(e.quote),
                turn=e.seg_from,
            )
            for e in evidence
        ],
        abstained=False,
        clarify=False,
        candidates=refs,
        when=query.when.label,
        label=_label(state),
    )


# --- admin health ------------------------------------------------------------------------------
class CheckOut(BaseModel):
    key: str
    state: Literal["ok", "warn", "fail", "info"]
    code: str
    counts: dict[str, int] = Field(default_factory=dict)


class HealthOut(BaseModel):
    on: bool
    checks: list[CheckOut]
    checkedAt: datetime


@admin_router.get("/health", response_model=HealthOut)
async def meeting_health(
    _: AdminPrincipal, user: CurrentUser, principal: CurrentPrincipal, source: UserSource, state: State
) -> HealthOut:
    """Live: can transcripts be listed with the admin's own sign-in (metadata only, never content)?
    From the tenant's readers (content-free counts, 14 days): speaker attribution, unavailability."""
    me = await self_email(source, principal.email)
    async with user_tx(state.engine, user, admin=True) as conn:
        on = await ingest.meeting_memory_on(conn)
        rows = (await conn.execute(text("select * from vanimo_private.meeting_ingest_health(14)"))).all()
        engine = await load_engine(conn, state.vault, user, self_email=me, extra_org_domains=_sample_domains(source))
    checks = [CheckOut(key="switch", state="ok" if on else "warn", code="on" if on else "off")]
    checks.append(await _live_check(source, engine, me))
    by: dict[tuple[str, str], int] = {(r.state, r.detail): r.n for r in rows}
    named, unnamed = by.get(("stored", "attributed"), 0), by.get(("stored", "unattributed"), 0)
    checks.append(
        CheckOut(
            key="speaker_attribution",
            state="ok" if named else ("warn" if unnamed else "info"),
            code="on" if named else ("off" if unnamed else "no_data"),
            counts={"named": named, "unattributed": unnamed},
        )
    )
    unavailable = {d: n for (s, d), n in by.items() if s == "unavailable"}
    checks.append(
        CheckOut(
            key="readers",
            state="warn" if unavailable.get("disabled") or unavailable.get("permission") else "info",
            code="counts",
            counts={
                "stored": named + unnamed,
                "no_transcript": sum(n for (s, _), n in by.items() if s == "no_transcript"),
                **{f"unavailable_{d}": n for d, n in unavailable.items()},
                "failed": sum(n for (s, _), n in by.items() if s == "failed"),
            },
        )
    )
    checks.append(CheckOut(key="access_policy", state="info", code="not_needed_delegated"))
    return HealthOut(on=on, checks=checks, checkedAt=datetime.now(UTC))


async def _live_check(source: Any, engine: Any, me: str) -> CheckOut:
    if source.kind == "sample":
        return CheckOut(key="transcript_access", state="info", code="sample_workspace")
    now = datetime.now(UTC)
    org = await source.org_domains()
    events = [
        e
        async for e in source.events(now - timedelta(days=14), now)
        if e.is_online and e.join_url and e.end < now and e.organizer
        and ingest._internal(e.organizer.domain, frozenset(org)) and not e.is_private and not engine.meeting(e).excluded
    ][-3:]  # fmt: skip
    if not events:
        return CheckOut(key="transcript_access", state="info", code="no_recent_meetings")
    listed = 0
    for e in events:
        try:
            listed += len(await source.meeting_transcripts(e))
        except TranscriptsUnavailable as exc:
            return CheckOut(key="transcript_access", state="fail", code=exc.reason)
    if listed:
        return CheckOut(key="transcript_access", state="ok", code="listed", counts={"transcripts": listed})
    return CheckOut(key="transcript_access", state="warn", code="none_found", counts={"meetings": len(events)})
