"""/api/controls — "Choose what Vanimo learns from" and My data controls (M1, architecture §6.5).

Flow: scan (header pass) → review the Sources index, exclude people/domains/chats/threads/
meetings with an impact preview, add never-send words → Finish or Skip. Nothing reads message
content before Finish/Skip (onboarding gate, vanimo.gates).

All responses are the caller's own data, decrypted for them only. Logs and audit events carry
rule IDs and counts — never labels, addresses or words.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from vanimo import audit
from vanimo.api.deps import CurrentUser, State, UserSource
from vanimo.controls import index as idx
from vanimo.controls.jobs import run_job
from vanimo.controls.neversend import Matcher, Term, folded_form, new_term_id, normalise, variants
from vanimo.controls.scan import run_scan
from vanimo.controls.store import (
    add_purge_job,
    bump_version,
    load_engine,
    load_matcher,
    load_terms,
    lock_user_controls,
)
from vanimo.db.session import UserRef, user_tx
from vanimo.gates import onboarding_state
from vanimo.logs import get_logger
from vanimo.sources.base import WorkspaceSource
from vanimo.sources.graph import EPOCH
from vanimo.state import AppState

log = get_logger("vanimo.controls")
router = APIRouter(prefix="/api/controls", tags=["controls"])

SourceKind = Literal["people", "domains", "threads", "chats", "meetings"]
RuleKind = Literal["person", "domain", "chat", "thread", "meeting", "series"]
MAX_TERMS = 500
# Words common enough that masking them weakens the persona; the user is warned, not blocked.
COMMON_WORDS = frozenset(
    "apple team project meeting client update review report plan data sales deal account call today "
    "tomorrow monday friday office leave travel budget invoice asha priya rahul amit neha raj ravi".split()
)


# --- status & scan ----------------------------------------------------------------------------


class ScanOut(BaseModel):
    status: str
    sourceKind: str
    startedAt: datetime
    finishedAt: datetime | None
    counts: dict[str, int]


class StatusOut(BaseModel):
    onboardingState: str
    reviewOutcome: str | None
    scan: ScanOut | None
    rules: int
    neverSendWords: int


async def _status(state: AppState, user: UserRef, source_kind: str) -> StatusOut:
    async with user_tx(state.engine, user) as conn:
        onboarding, outcome = await onboarding_state(conn, source_kind)
        # Only scans of the source in use count (switching sample to Microsoft 365 starts over).
        scan = (
            await conn.execute(
                text("select * from vanimo.source_scans where source_kind = :k order by started_at desc limit 1"),
                {"k": source_kind},
            )
        ).first()
        rules = (
            await conn.execute(text("select count(*) from vanimo.exclusion_rules where status = 'active'"))
        ).scalar_one()
        words = (await conn.execute(text("select count(*) from vanimo.never_send_terms"))).scalar_one()
    return StatusOut(
        onboardingState=onboarding,
        reviewOutcome=outcome,
        scan=ScanOut(
            status=scan.status,
            sourceKind=scan.source_kind,
            startedAt=scan.started_at,
            finishedAt=scan.finished_at,
            counts={k: v for k, v in scan.counts.items() if isinstance(v, int)},
        )
        if scan
        else None,
        rules=rules,
        neverSendWords=words,
    )


@router.get("/status", response_model=StatusOut)
async def status(user: CurrentUser, source: UserSource, state: State) -> StatusOut:
    return await _status(state, user, source.kind)


@router.post("/scan", response_model=StatusOut, status_code=202)
async def start_scan(user: CurrentUser, source: UserSource, state: State, request: Request) -> StatusOut:
    """Starts the header pass in the background; poll /status. Sample workspaces finish instantly."""
    key = f"scan:{user.user_id}"
    async with user_tx(state.engine, user) as conn:
        # Also catches a scan started by another API process (the sweeper fails stale ones).
        running = (
            await conn.execute(
                text(
                    "select 1 from vanimo.source_scans where status = 'running' "
                    "and started_at > now() - interval '120 minutes' limit 1"
                )
            )
        ).first()
    if running or any(t.get_name() == key and not t.done() for t in state.tasks):
        raise HTTPException(409, detail={"error": "scan_running"})
    # A long background pass gets patient throttling retries (interactive calls use short ones).
    background = getattr(source, "for_background", None)
    task = state.spawn(run_scan(state.engine, state.vault, user, background() if background else source))
    task.set_name(key)
    async with user_tx(state.engine, user) as conn:
        await audit.record(conn, user, "controls.scan_started", request_id=request.state.request_id)
    if source.kind == "sample":
        # Instant for sample data: return the finished state. A failure is recorded on the scan row
        # (status "failed"), which /status reports, so it isn't re-raised here.
        await asyncio.gather(task, return_exceptions=True)
    return await _status(state, user, source.kind)


# --- sources ----------------------------------------------------------------------------------


class SourceItem(BaseModel):
    id: str
    kind: RuleKind
    label: str
    detail: str | None = None
    counts: dict[str, int] = Field(default_factory=dict)
    lastActivity: datetime | None = None
    flags: list[str] = Field(default_factory=list)  # pre-flagged reasons to review
    excluded: bool
    ruleId: str | None = None  # the user's own rule on this item (removable here)
    via: list[str] = Field(default_factory=list)
    locked: bool = False  # excluded by the organisation


async def _context(
    state: AppState, user: UserRef, source: WorkspaceSource
) -> tuple[idx.IndexView, idx.Evaluator, Matcher]:
    async with user_tx(state.engine, user) as conn:
        view = await idx.load_index(conn, state.vault, user)
        engine = await load_engine(
            conn,
            state.vault,
            user,
            extra_org_domains=await source.org_domains() if source.kind == "sample" else (),
        )
        matcher = await load_matcher(conn, state.vault, user)
        accounts = (await conn.execute(text("select id, name_enc from vanimo.client_accounts"))).all()
    names = {str(a.id): state.vault.decrypt_tenant(user.tenant_id, a.name_enc, "account_name") or "" for a in accounts}
    return view, idx.Evaluator(view, engine, names, display_masker(matcher)), matcher


def display_masker(matcher: Matcher):  # type: ignore[no-untyped-def]
    """Addresses are stored (encrypted) as identifiers; a never-send word inside one is still
    masked wherever it is displayed."""

    def shown(value: str) -> str:
        return idx.render_removed(matcher.mask(value)[0]) or value

    return shown


async def _matcher(state: AppState, user: UserRef) -> Matcher:
    async with user_tx(state.engine, user) as conn:
        return await load_matcher(conn, state.vault, user)


def _item(kind: RuleKind, item_id: Any, label: str, st: idx.Status, **kw: Any) -> SourceItem:
    return SourceItem(
        id=str(item_id), kind=kind, label=label, excluded=st.excluded, ruleId=st.direct_rule_id, via=st.via,
        locked=st.locked, **kw,
    )  # fmt: skip


async def _index_matches_source(state: AppState, user: UserRef, source_kind: str) -> bool:
    async with user_tx(state.engine, user) as conn:
        latest = (
            await conn.execute(
                text(
                    "select source_kind from vanimo.source_scans where status = 'done' "
                    "order by finished_at desc limit 1"
                )
            )
        ).scalar_one_or_none()
    return latest is None or latest == source_kind


@router.get("/sources", response_model=list[SourceItem])
async def list_sources(
    user: CurrentUser, source: UserSource, state: State, kind: Annotated[SourceKind, Query()]
) -> list[SourceItem]:
    view, ev, matcher = await _context(state, user, source)
    if not await _index_matches_source(state, user, source.kind):
        return []  # the index belongs to the other data source; a new scan replaces it
    mask = display_masker(matcher)

    def shown(value: str | None) -> str | None:
        return mask(value) if value else value

    items: list[SourceItem] = []
    if kind == "people":
        for p in sorted(view.people.values(), key=lambda p: -(p.sent + p.chats + p.meetings)):
            flags = (["personal email"] if p.consumer else []) + ([] if p.internal else ["external"])
            items.append(
                _item("person", p.id, shown(p.label) or p.label, ev.person(p), detail=shown(p.email),
                      lastActivity=p.last, flags=flags,
                      counts={"emails": p.sent, "chats": p.chats, "meetings": p.meetings})
            )  # fmt: skip
    elif kind == "domains":
        groups: dict[str, list[idx.Person]] = {}
        for p in view.people.values():
            groups.setdefault(p.domain_hash, []).append(p)
        for dh, people in sorted(groups.items(), key=lambda g: -sum(p.sent for p in g[1])):
            first = people[0]
            flags = (["personal email"] if first.consumer else []) + (["your organisation"] if first.internal else [])
            items.append(
                _item("domain", first.id, shown(first.domain) or "", ev.domain(first.domain, dh),
                      detail=f"{len(people)} {'person' if len(people) == 1 else 'people'}", flags=flags,
                      counts={"people": len(people), "emails": sum(p.sent for p in people)},
                      lastActivity=max((p.last for p in people if p.last), default=None))
            )  # fmt: skip
    elif kind == "threads":
        for t in sorted(view.threads.values(), key=lambda t: t.last or EPOCH, reverse=True):
            items.append(
                _item("thread", t.id, idx.render_removed(t.subject) or "(no subject)", ev.thread(t),
                      counts={"emails": t.count, "people": len(t.people)}, lastActivity=t.last,
                      flags=["forward"] if t.forward else [])
            )  # fmt: skip
    elif kind == "chats":
        for c in sorted(view.chats.values(), key=lambda c: c.last or EPOCH, reverse=True):
            flags = (["hidden in Teams"] if c.hidden else []) + (["large group"] if c.members >= idx.LARGE_CHAT else [])
            items.append(
                _item("chat", c.id, c.label, ev.chat(c), detail={"oneOnOne": "1:1 chat", "group": "Group chat",
                      "meeting": "Meeting chat"}[c.chat_type], counts={"members": c.members}, lastActivity=c.last,
                      flags=flags)
            )  # fmt: skip
    else:
        seen_series: set[str] = set()
        for m in sorted(view.meetings.values(), key=lambda m: m.start, reverse=True):
            subject = idx.render_removed(m.subject) or "(no subject)"
            if m.series_hash:
                if m.series_hash in seen_series:
                    continue
                seen_series.add(m.series_hash)
                occurrences = sum(1 for x in view.meetings.values() if x.series_hash == m.series_hash)
                items.append(
                    _item("series", m.id, subject, ev.meeting(m, as_series=True), detail="Recurring series",
                          counts={"occurrences": occurrences, "attendees": len(m.people)}, lastActivity=m.start,
                          flags=["private"] if m.private else [])
                )  # fmt: skip
            else:
                items.append(
                    _item("meeting", m.id, subject, ev.meeting(m), detail="Meeting", lastActivity=m.start,
                          counts={"attendees": len(m.people)}, flags=["private"] if m.private else [])
                )  # fmt: skip
    return items


# --- impact & rules ---------------------------------------------------------------------------


class ImpactIn(BaseModel):
    kind: RuleKind
    id: uuid.UUID


@router.post("/impact")
async def impact(body: ImpactIn, user: CurrentUser, state: State) -> dict[str, Any]:
    async with user_tx(state.engine, user) as conn:
        view = await idx.load_index(conn, state.vault, user)
        by_person, thread_counts = await idx.message_links(conn)
    _key_hash(view, body.kind, body.id)  # 404 if the item isn't in the caller's index
    return idx.impact(view, body.kind, body.id, by_person, thread_counts)


def _key_hash(view: idx.IndexView, kind: str, item_id: uuid.UUID) -> str:
    try:
        if kind == "person":
            return view.people[item_id].key_hash
        if kind == "domain":
            return view.people[item_id].domain_hash
        if kind == "thread":
            return view.threads[item_id].key_hash
        if kind == "chat":
            return view.chats[item_id].key_hash
        if kind == "meeting":
            return view.meetings[item_id].key_hash
        series = view.meetings[item_id].series_hash
        if series:
            return series
    except KeyError:
        pass
    raise HTTPException(404, detail={"error": "source_not_found"})


class RuleIn(BaseModel):
    kind: RuleKind
    id: uuid.UUID
    # For person/domain rules: group chats to keep using even though the person is in them (D5).
    exceptChatIds: list[uuid.UUID] = Field(default_factory=list, max_length=500)


class RuleOut(BaseModel):
    id: str
    kind: str
    label: str
    createdAt: datetime
    exceptions: int


def _start_job(state: AppState, user: UserRef, job_id: str, reason: str) -> None:
    """Call only after the transaction that created the job has committed."""
    state.spawn(run_job(state.engine, state.vault, user, job_id, reason))


@router.post("/rules", response_model=RuleOut, status_code=201)
async def add_rule(body: RuleIn, user: CurrentUser, state: State, request: Request) -> RuleOut:
    try:
        return await _add_rule(body, user, state, request)
    except IntegrityError:  # the same rule added twice at once: the unique index catches the second
        raise HTTPException(409, detail={"error": "already_excluded"}) from None


async def _add_rule(body: RuleIn, user: UserRef, state: AppState, request: Request) -> RuleOut:
    async with user_tx(state.engine, user) as conn:
        view = await idx.load_index(conn, state.vault, user)
        key_hash = _key_hash(view, body.kind, body.id)
        if body.exceptChatIds and body.kind not in ("person", "domain"):
            raise HTTPException(422, detail={"error": "exceptions_only_for_people"})
        exceptions = [view.chats[c].key_hash for c in body.exceptChatIds if c in view.chats]
        existing = (
            await conn.execute(
                text("select id from vanimo.exclusion_rules where kind = :k and key_hash = :h and status = 'active'"),
                {"k": body.kind, "h": key_hash},
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(409, detail={"error": "already_excluded", "ruleId": str(existing)})
        row = (
            await conn.execute(
                text(
                    "insert into vanimo.exclusion_rules (tenant_id, owner_user_id, kind, key_hash) "
                    "values (:t, :u, :k, :h) returning id, created_at"
                ),
                {"t": user.tenant_id, "u": user.user_id, "k": body.kind, "h": key_hash},
            )
        ).one()
        if exceptions:
            await conn.execute(
                text(
                    "insert into vanimo.exclusion_exceptions (tenant_id, owner_user_id, rule_id, chat_hash) "
                    "values (:t, :u, :r, :c)"
                ),
                [{"t": user.tenant_id, "u": user.user_id, "r": row.id, "c": c} for c in dict.fromkeys(exceptions)],
            )
        await bump_version(conn, user)
        await audit.record(conn, user, "controls.rule_added", target_kind=body.kind, target_ref=str(row.id),
                           request_id=request.state.request_id)  # fmt: skip
        job_id = await add_purge_job(conn, user, "exclusion_added")
    _start_job(state, user, job_id, "exclusion_added")
    log.info("controls.rule_added", count=len(exceptions))
    matcher_labels = view.by_hash(display_masker(await _matcher(state, user)))
    return RuleOut(id=str(row.id), kind=body.kind, label=matcher_labels.get((body.kind, key_hash), body.kind),
                   createdAt=row.created_at, exceptions=len(exceptions))  # fmt: skip


@router.get("/rules", response_model=list[RuleOut])
async def list_rules(user: CurrentUser, state: State) -> list[RuleOut]:
    async with user_tx(state.engine, user) as conn:
        view = await idx.load_index(conn, state.vault, user)
        rows = (
            await conn.execute(
                text(
                    "select r.id, r.kind, r.key_hash, r.created_at, count(e.chat_hash) as n "
                    "from vanimo.exclusion_rules r left join vanimo.exclusion_exceptions e on e.rule_id = r.id "
                    "where r.status = 'active' group by r.id order by r.created_at desc"
                )
            )
        ).all()
    labels = view.by_hash(display_masker(await _matcher(state, user)))
    return [
        RuleOut(id=str(r.id), kind=r.kind, label=labels.get((r.kind, r.key_hash), "(no longer in your sources)"),
                createdAt=r.created_at, exceptions=r.n)
        for r in rows
    ]  # fmt: skip


@router.delete("/rules/{rule_id}", status_code=204)
async def remove_rule(rule_id: uuid.UUID, user: CurrentUser, state: State, request: Request) -> None:
    """Un-exclude: the source is used again from now on. Nothing deleted earlier is restored."""
    async with user_tx(state.engine, user) as conn:
        done = (
            await conn.execute(
                text(
                    "update vanimo.exclusion_rules set status = 'revoked', revoked_at = now() "
                    "where id = :id and status = 'active' returning id"
                ),
                {"id": rule_id},
            )
        ).first()
        if not done:
            raise HTTPException(404, detail={"error": "rule_not_found"})
        await bump_version(conn, user)
        await audit.record(conn, user, "controls.rule_removed", target_kind="rule", target_ref=str(rule_id),
                           request_id=request.state.request_id)  # fmt: skip
        job_id = await add_purge_job(conn, user, "exclusion_removed")
    _start_job(state, user, job_id, "exclusion_removed")


# --- never-send words ---------------------------------------------------------------------------


class TermPreviewIn(BaseModel):
    text: str = Field(min_length=1, max_length=100)
    kind: Literal["word", "name", "codename"] = "word"


class TermPreviewOut(BaseModel):
    variants: list[str]
    # What the optional Hinglish folding reduces the word to (e.g. "Sharmaa" -> "sharma"); the
    # user opts in per word after seeing it. None when folding doesn't apply.
    foldedForm: str | None
    appearsIn: int
    appearsInWithFolds: int
    commonWord: bool


def _index_texts(view: idx.IndexView) -> list[str]:
    texts: list[str] = []
    texts += [p.name for p in view.people.values() if p.name]
    texts += [t.subject for t in view.threads.values() if t.subject]
    texts += [c.label for c in view.chats.values()]
    texts += [m.subject for m in view.meetings.values() if m.subject]
    return texts


@router.post("/never-send/preview", response_model=TermPreviewOut)
async def preview_term(body: TermPreviewIn, user: CurrentUser, state: State) -> TermPreviewOut:
    """Variants to confirm and how many stored items the word appears in. The word is not stored."""
    async with user_tx(state.engine, user) as conn:
        view = await idx.load_index(conn, state.vault, user)
    texts = _index_texts(view)
    plain = Matcher([Term("00000000", body.text, body.kind)])
    folded = Matcher([Term("00000000", body.text, body.kind, folds=True)])
    appears = sum(1 for t in texts if plain.count(t))
    appears_folded = sum(1 for t in texts if folded.count(t))
    words = body.text.strip().lower().split()
    common = len(body.text.strip()) <= 3 or any(w in COMMON_WORDS for w in words)
    return TermPreviewOut(
        variants=variants(body.text, body.kind),
        foldedForm=folded_form(body.text),
        appearsIn=appears,
        appearsInWithFolds=appears_folded,
        commonWord=common,
    )


class TermIn(TermPreviewIn):
    # Extra spellings the user typed or confirmed (e.g. Devanagari): matched exactly like the term.
    variants: list[str] = Field(default_factory=list, max_length=20)
    allowInDrafts: bool = False
    folds: bool = False  # also catch Hinglish spellings (shown in the preview first)


class TermOut(BaseModel):
    id: str
    text: str
    kind: str
    variants: list[str]
    allowInDrafts: bool
    folds: bool = False
    createdAt: datetime


def _term_out(t: dict[str, Any]) -> TermOut:
    return TermOut(id=t["id"], text=t["text"], kind=t["kind"], variants=t["variants"],
                   allowInDrafts=t["allow_in_drafts"], folds=t["folds"], createdAt=t["created_at"])  # fmt: skip


@router.get("/never-send", response_model=list[TermOut])
async def list_terms(user: CurrentUser, state: State) -> list[TermOut]:
    async with user_tx(state.engine, user) as conn:
        return [_term_out(t) for t in await load_terms(conn, state.vault, user)]


@router.post("/never-send", response_model=TermOut, status_code=201)
async def add_term(body: TermIn, user: CurrentUser, state: State, request: Request) -> TermOut:
    if not normalise(body.text)[0].strip():
        raise HTTPException(422, detail={"error": "empty_word"})  # spaces or invisible characters only
    extra = [v.strip() for v in body.variants if v.strip() and len(v.strip()) <= 100]
    t, u = user.tenant_id, user.user_id
    async with user_tx(state.engine, user) as conn:
        await lock_user_controls(conn, user)  # two adds at once can't both pass the checks below
        count = (await conn.execute(text("select count(*) from vanimo.never_send_terms"))).scalar_one()
        if count >= MAX_TERMS:
            raise HTTPException(422, detail={"error": "too_many_words"})
        existing = await load_terms(conn, state.vault, user)
        if any(e["text"].strip().casefold() == body.text.strip().casefold() for e in existing):
            raise HTTPException(409, detail={"error": "already_listed"})
        row = (
            await conn.execute(
                text(
                    "insert into vanimo.never_send_terms (tenant_id, owner_user_id, term_id, term_enc, variants_enc, "
                    "kind, allow_in_drafts, folds) values (:t, :u, :tid, :te, :ve, :k, :a, :f) returning id, created_at"
                ),
                {
                    "t": t, "u": u, "tid": new_term_id(),
                    "te": state.vault.encrypt_user(t, u, body.text.strip(), "ns_term"),
                    "ve": state.vault.encrypt_user(t, u, json.dumps(extra), "ns_variants"),
                    "k": body.kind, "a": body.allowInDrafts, "f": body.folds,
                },
            )
        ).one()  # fmt: skip
        await bump_version(conn, user)
        await audit.record(conn, user, "controls.word_added", target_kind="never_send", target_ref=str(row.id),
                           request_id=request.state.request_id)  # fmt: skip
        job_id = await add_purge_job(conn, user, "term_added")
    _start_job(state, user, job_id, "term_added")
    return TermOut(id=str(row.id), text=body.text.strip(), kind=body.kind, variants=extra,
                   allowInDrafts=body.allowInDrafts, folds=body.folds, createdAt=row.created_at)  # fmt: skip


class TermPatch(BaseModel):
    allowInDrafts: bool


@router.patch("/never-send/{term_id}", status_code=204)
async def update_term(term_id: uuid.UUID, body: TermPatch, user: CurrentUser, state: State, request: Request) -> None:
    async with user_tx(state.engine, user) as conn:
        done = (
            await conn.execute(
                text("update vanimo.never_send_terms set allow_in_drafts = :a where id = :id returning id"),
                {"a": body.allowInDrafts, "id": term_id},
            )
        ).first()
        if not done:
            raise HTTPException(404, detail={"error": "word_not_found"})
        await bump_version(conn, user)
        await audit.record(conn, user, "controls.word_changed", target_kind="never_send", target_ref=str(term_id),
                           request_id=request.state.request_id)  # fmt: skip


@router.delete("/never-send/{term_id}", status_code=204)
async def delete_term(term_id: uuid.UUID, user: CurrentUser, state: State, request: Request) -> None:
    """Stops matching the word from now on. Text masked earlier stays masked."""
    async with user_tx(state.engine, user) as conn:
        done = (
            await conn.execute(text("delete from vanimo.never_send_terms where id = :id returning id"), {"id": term_id})
        ).first()
        if not done:
            raise HTTPException(404, detail={"error": "word_not_found"})
        await bump_version(conn, user)
        await audit.record(conn, user, "controls.word_removed", target_kind="never_send", target_ref=str(term_id),
                           request_id=request.state.request_id)  # fmt: skip
        job_id = await add_purge_job(conn, user, "term_removed")
    _start_job(state, user, job_id, "term_removed")


# --- review gate & receipts ---------------------------------------------------------------------


class ReviewIn(BaseModel):
    outcome: Literal["finished", "skipped"]


@router.post("/review", response_model=StatusOut)
async def complete_review(
    body: ReviewIn, user: CurrentUser, source: UserSource, state: State, request: Request
) -> StatusOut:
    """Finish or Skip the review *for the current data source*. Only after this may Vanimo read
    message content from that source (M2 backfill)."""
    async with user_tx(state.engine, user) as conn:
        if body.outcome == "finished":
            done_scan = (
                await conn.execute(
                    text("select 1 from vanimo.source_scans where status = 'done' and source_kind = :k limit 1"),
                    {"k": source.kind},
                )
            ).first()
            if not done_scan:
                raise HTTPException(409, detail={"error": "scan_not_done"})
        await conn.execute(
            text(
                "update vanimo.users set onboarding_state = 'review_done', review_outcome = :o, "
                "review_completed_at = now(), reviewed_source_kind = :k, "
                "reviewed_sources = (select array_agg(distinct s) from unnest(reviewed_sources || cast(:k as text)) s)"
            ),
            {"o": body.outcome, "k": source.kind},
        )
        await audit.record(conn, user, f"controls.review_{body.outcome}", request_id=request.state.request_id)
    return await _status(state, user, source.kind)


class ReceiptOut(BaseModel):
    id: str
    reason: str
    status: str
    requestedAt: datetime
    completedAt: datetime | None
    counts: dict[str, Any]
    needsAttention: bool = False  # failed after every automatic retry


@router.get("/receipts", response_model=list[ReceiptOut])
async def receipts(user: CurrentUser, state: State) -> list[ReceiptOut]:
    async with user_tx(state.engine, user) as conn:
        rows = (await conn.execute(text("select * from vanimo.purge_jobs order by requested_at desc limit 100"))).all()
    return [
        ReceiptOut(id=str(r.id), reason=r.reason, status=r.status, requestedAt=r.requested_at,
                   completedAt=r.completed_at, counts=r.counts,
                   needsAttention=r.status == "failed" and r.attempts >= 3)
        for r in rows
    ]  # fmt: skip


@router.post("/receipts/{job_id}/retry", response_model=ReceiptOut)
async def retry_receipt(job_id: uuid.UUID, user: CurrentUser, state: State, request: Request) -> ReceiptOut:
    """Run a failed purge or scrub again (they are idempotent)."""
    async with user_tx(state.engine, user) as conn:
        row = (
            await conn.execute(
                text(
                    "update vanimo.purge_jobs set status = 'running', attempts = 0, "
                    "lease_until = now() + interval '10 minutes' where id = :id and status = 'failed' "
                    "returning id, reason"
                ),
                {"id": job_id},
            )
        ).first()
        if not row:
            raise HTTPException(404, detail={"error": "no_failed_job"})
        await audit.record(conn, user, "controls.job_retried", target_kind="purge_job", target_ref=str(job_id),
                           request_id=request.state.request_id)  # fmt: skip
    await run_job(state.engine, state.vault, user, str(row.id), row.reason)
    async with user_tx(state.engine, user) as conn:
        r = (await conn.execute(text("select * from vanimo.purge_jobs where id = :id"), {"id": job_id})).one()
    return ReceiptOut(id=str(r.id), reason=r.reason, status=r.status, requestedAt=r.requested_at,
                      completedAt=r.completed_at, counts=r.counts, needsAttention=False)  # fmt: skip
