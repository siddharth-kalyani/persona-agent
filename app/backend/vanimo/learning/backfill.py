"""The learning backfill (architecture §9.2, MVP plan M2): read the user's own sent emails and
chat messages from allowed sources only, redact them to L1, label them and store them.

Order of checks for every item (§6.5 two-phase fetch):
  1. the onboarding review is done for this source (gate);
  2. the exclusion engine allows the item from its *metadata* — only then is its text read;
  3. the message it replied to is used as context only if its sender is allowed too;
  4. L0 text is redacted in memory (never-send → Tier R → tokens → verify, fail-closed);
  5. before storing, the user's controls version is re-checked: a rule or word added while the
     run was reading wins, and the run starts again with the new controls.

Nothing but L1 is stored, vault-encrypted per user, with HMAC lineage for later purges.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from vanimo.controls.engine import ExclusionEngine, Hasher
from vanimo.controls.neversend import Matcher
from vanimo.controls.scan import CALENDAR_AHEAD, CALENDAR_BACK, meeting_links
from vanimo.controls.store import hasher_for, load_engine, load_matcher, lock_user_controls
from vanimo.db.session import UserRef, user_tx
from vanimo.gates import require_review_done
from vanimo.learning import labels
from vanimo.learning.embed import embed
from vanimo.logs import get_logger
from vanimo.redaction.parse import strip_signature_noise
from vanimo.redaction.pipeline import BackstopUnavailable, Gazetteer, Person, Redacted, RedactionBlocked, Redactor
from vanimo.sources.base import Address, ChatMessage, MessageContent, WorkspaceSource
from vanimo.vault import Vault

log = get_logger("vanimo.learning")

MAX_ATTEMPTS = 3
CONTEXT_MESSAGES = 3  # chat: at most this many messages before the user's reply
HELD_OUT_PERCENT = 15  # deterministic eval split by item hash
HEARTBEAT_EVERY = 50  # items between heartbeats


class LearningRunning(Exception):
    pass


class ControlsChanged(Exception):
    pass


class RunCancelled(Exception):
    """The run row is no longer 'running' (the user deleted what was learned, or the sweeper
    timed it out): nothing more is stored."""


@dataclass
class Item:
    channel: str
    item_hash: str
    thread_hash: str
    people: list[tuple[str, list[str]]]
    sent_at: datetime
    subject: Redacted | None
    text: Redacted
    context: Redacted | None
    relationship: str
    intent: str
    language: str
    word_count: int
    meeting_hash: str | None = None
    series_hash: str | None = None
    # The conversation or chat it came from (in memory only; a commitment found in it keeps it
    # encrypted, so a follow-up can be drafted in the same place).
    ref: str | None = None


@dataclass
class Collected:
    items: list[Item] = field(default_factory=list)
    counts: Counter[str] = field(default_factory=Counter)


async def controls_version(conn: AsyncConnection) -> int:
    v = (await conn.execute(text("select version from vanimo.controls_state"))).scalar_one_or_none()
    return int(v or 0)


async def start_run(engine: AsyncEngine, ref: UserRef, source_kind: str) -> str:
    """Create the run row; at most one running per user (a unique index enforces it)."""
    try:
        async with user_tx(engine, ref) as conn:
            return str(
                (
                    await conn.execute(
                        text(
                            "insert into vanimo.learning_runs (tenant_id, owner_user_id, source_kind, status) "
                            "values (:t, :u, :k, 'running') returning id"
                        ),
                        {"t": ref.tenant_id, "u": ref.user_id, "k": source_kind},
                    )
                ).scalar_one()
            )
    except IntegrityError as exc:
        raise LearningRunning() from exc


async def run_learning(
    engine: AsyncEngine,
    vault: Vault,
    ref: UserRef,
    source: WorkspaceSource,
    *,
    self_email: str,
    run_id: str,
    extractor: Any = None,
    tz: Any = None,
) -> None:
    """Runs to completion and records the outcome on the run row (never raises). `extractor` and
    `tz`: how promises are found in what was learned (M5 commitments; offline rules by default)."""
    from zoneinfo import ZoneInfo

    from vanimo.commitments import store as commitments
    from vanimo.commitments.extract import OfflineExtractor
    from vanimo.learning import persona  # style cards are rebuilt after every run
    from vanimo.learning.evaluate import offline_baseline

    kind = source.kind
    started_at = datetime.now(UTC)
    try:
        await require_review_done(engine, ref, kind)
        for attempt in range(1, MAX_ATTEMPTS + 1):
            async with user_tx(engine, ref) as conn:
                version = await controls_version(conn)
                ex_engine = await load_engine(
                    conn, vault, ref, self_email=self_email, extra_org_domains=await _sample_domains(source)
                )
                matcher = await load_matcher(conn, vault, ref)
            beat = _heartbeat(engine, ref, run_id)
            collected = await collect(source, ex_engine, matcher, hasher_for(vault, ref), self_email, beat=beat)
            try:
                await persist(engine, vault, ref, kind, run_id, collected.items, version)
                break
            except ControlsChanged:
                log.info("learning.controls_changed", attempt=attempt)
                if attempt == MAX_ATTEMPTS:
                    raise
        cards = await persona.rebuild(engine, vault, ref, kind)
        metrics = await offline_baseline(engine, vault, ref, kind)
        try:
            found = await commitments.from_learning(
                engine,
                vault,
                ref,
                kind,
                collected.items,
                version,
                extractor or OfflineExtractor(),
                tz or ZoneInfo("UTC"),
                started_at,
                beat=beat,  # each model call can be slow: keep the run alive (and stop if it was cancelled)
            )
        except Exception as exc:  # the ledger is extra: learning itself succeeded
            log.warning("learning.commitments_failed", error_type=type(exc).__name__)
            found = None
        counts = dict(collected.counts) | {"stored": len(collected.items), "style_cards": cards}
        counts["names_redacted"] = int(matcher.redact_names)  # F12: which choice this run learned with
        counts["commitments"] = found.stored if found else 0
        counts |= {f"eval_{k}": v for k, v in metrics.items() if isinstance(v, int | float)}
        await _finish(engine, ref, run_id, "done", counts, version)
        log.info("learning.done", count=len(collected.items))
    except RunCancelled:
        log.info("learning.cancelled")  # deleted or timed out meanwhile: the row already says so
    except Exception as exc:
        log.error("learning.failed", error_type=type(exc).__name__)
        await _finish(engine, ref, run_id, "failed", {}, None, error=_error_code(exc))


async def _sample_domains(source: WorkspaceSource) -> frozenset[str]:
    return await source.org_domains() if source.kind == "sample" else frozenset()


def _error_code(exc: Exception) -> str:
    code = getattr(exc, "code", None) or type(exc).__name__
    return str(code)[:80]


def _heartbeat(engine: AsyncEngine, ref: UserRef, run_id: str) -> Callable[[], Awaitable[None]]:
    """Every call marks the run alive; the sweeper fails runs silent for 2 hours. A run that was
    cancelled meanwhile (the user deleted what was learned) stops here."""

    async def beat() -> None:
        async with user_tx(engine, ref) as conn:
            alive = (
                await conn.execute(
                    text(
                        "update vanimo.learning_runs set heartbeat_at = now() "
                        "where id = :id and status = 'running' returning id"
                    ),
                    {"id": run_id},
                )
            ).first()
        if not alive:
            raise RunCancelled()

    return beat


async def _finish(
    engine: AsyncEngine,
    ref: UserRef,
    run_id: str,
    status: str,
    counts: dict[str, Any],
    version: int | None,
    *,
    error: str | None = None,
) -> None:
    # Only a run that is still running: a cancelled or swept run keeps its outcome.
    async with user_tx(engine, ref) as conn:
        await conn.execute(
            text(
                "update vanimo.learning_runs set status = :s, finished_at = now(), counts = cast(:c as jsonb), "
                "controls_version = :v, error_code = :e where id = :id and status = 'running'"
            ),
            {"s": status, "c": json.dumps(counts), "v": version, "e": error, "id": run_id},
        )


# --- collect --------------------------------------------------------------------------------
async def build_gazetteer(source: WorkspaceSource, self_email: str) -> tuple[Gazetteer, dict[str, Any]]:
    """Names from the user's profile, manager, reports and every header and roster (S5)."""
    profile = await source.profile()
    manager = await source.manager()
    reports = await source.direct_reports()
    g = Gazetteer(me=Person(profile.display_name or self_email.split("@")[0], self_email.lower()))
    if manager:
        g.add(manager.display_name, manager.email)
    for r in reports:
        g.add(r.name, r.email)
    async for h in source.sent_headers():
        for a in h.participants:
            g.add(a.name, a.email)
    async for c in source.chats():
        for a in c.members:
            g.add(a.name, a.email)
    directory = {
        "manager": (manager.email or "").lower() if manager else None,
        "reports": frozenset(r.email.lower() for r in reports),
        "org_domains": await source.org_domains(),
    }
    return g, directory


async def _no_beat() -> None:
    return None


async def collect(
    source: WorkspaceSource,
    ex_engine: ExclusionEngine,
    matcher: Matcher,
    hasher: Hasher,
    self_email: str,
    *,
    beat: Callable[[], Awaitable[None]] = _no_beat,
) -> Collected:
    me = self_email.lower()
    gazetteer, directory = await build_gazetteer(source, me)
    redactor = Redactor(matcher, gazetteer, hasher)
    out = Collected()
    seen = 0

    async def tick() -> None:
        nonlocal seen
        seen += 1
        if seen % HEARTBEAT_EVERY == 0:
            await beat()

    def lineage(people: list[Address]) -> list[tuple[str, list[str]]]:
        uniq = {a.email.lower(): a for a in people if a.email and a.email.lower() != me}
        return [(hasher("person", e), ex_engine.domain_hashes(a.domain)) for e, a in sorted(uniq.items())]

    async def label_and_add(
        channel: str,
        item_id: str,
        thread_hash: str,
        audience: list[Address],
        extra: list[Address],
        sent_at: datetime,
        subject: str | None,
        body: str,
        context: str | None,
        *,
        hidden: bool = False,
        meeting: tuple[str | None, str | None] = (None, None),
        ref: str | None = None,
    ) -> None:
        body = strip_signature_noise(body).strip()
        if not body:
            out.counts["empty"] += 1
            return
        try:
            red = await redactor.redact(body, hidden_seen=hidden)
        except BackstopUnavailable:
            raise  # the run fails and can be retried: items are never skipped for an outage
        except RedactionBlocked as e:
            out.counts[f"blocked_{e.reason}"] += 1
            return
        ctx = None
        if context:
            try:
                ctx = await redactor.redact(context)
            except BackstopUnavailable:
                raise
            except RedactionBlocked as e:
                out.counts[f"context_blocked_{e.reason}"] += 1
        subj = None
        if subject:
            try:
                subj = await redactor.redact(subject)
            except BackstopUnavailable:
                raise
            except RedactionBlocked:
                out.counts["subject_blocked"] += 1
        ws = labels.words(red.text)
        out.items.append(
            Item(
                channel=channel,
                item_hash=hasher("item", f"{channel}:{item_id}"),
                thread_hash=thread_hash,
                people=lineage(audience + extra),
                sent_at=sent_at,
                subject=subj,
                text=red,
                context=ctx,
                relationship=labels.relationship(
                    [a for a in audience if a.email.lower() != me],
                    manager=directory["manager"],
                    reports=directory["reports"],
                    org_domains=directory["org_domains"],
                ),
                intent=labels.intent(red.text),
                language=labels.language(red.text),
                word_count=len(ws),
                meeting_hash=meeting[0],
                series_hash=meeting[1],
                ref=ref,
            )
        )
        out.counts[f"{channel}_learned"] += 1

    # Emails, two-phase (§6.5 X2): sent headers and thread headers first, metadata only; text is
    # fetched only for the user's allowed messages and the one message each replied to.
    allowed: dict[str, Any] = {}
    async for h in source.sent_headers():
        if h.id in allowed:
            continue
        if ex_engine.message(h).excluded:
            out.counts["email_excluded"] += 1
            continue
        allowed[h.id] = h
    by_thread: dict[str, list[str]] = {}
    for h in allowed.values():
        by_thread.setdefault(h.conversation_id, []).append(h.id)
    for conv, ids in by_thread.items():
        headers = sorted(await source.thread_headers(conv), key=lambda x: x.sent_at)
        sent_at = {x.id: x.sent_at for x in headers}
        for mid in ids:
            await tick()
            when = sent_at.get(mid) or allowed[mid].sent_at
            prior = [x for x in headers if x.direction == "received" and x.sent_at < when]
            ctx_header = prior[-1] if prior else None
            extra: list[Address] = []
            if ctx_header is not None:
                # Everyone on the message replied to counts, not only its sender: a cc'd
                # excluded client keeps that message out.
                if ex_engine.people_reasons(ctx_header.participants):
                    out.counts["context_excluded"] += 1
                    ctx_header = None
                else:
                    extra = list(ctx_header.participants)
            m: MessageContent | None = await source.message(mid)
            if m is None:
                out.counts["email_missing"] += 1
                continue
            ctx_msg = await source.message(ctx_header.id) if ctx_header else None
            h = allowed[mid]
            await label_and_add(
                "email",
                mid,
                hasher("thread", conv),
                list(h.participants),
                extra,
                m.sent_at,
                m.subject,
                m.body,
                ctx_msg.body if ctx_msg else None,
                hidden=m.hidden or bool(ctx_msg and ctx_msg.hidden),
                ref=conv,
            )

    # Chats: the roster decides; context is the run of messages just before the user's reply.
    # A meeting chat is tied to its meeting by the join link; one whose meeting isn't in the
    # calendar window can't be checked against meeting rules, so it isn't read (fail-closed).
    now = datetime.now(UTC)
    by_url = meeting_links([e async for e in source.events(now - CALENDAR_BACK, now + CALENDAR_AHEAD)])
    async for c in source.chats():
        meeting_ids = by_url.get(c.join_url or "") if c.chat_type == "meeting" else None
        if c.chat_type == "meeting" and meeting_ids is None:
            out.counts["chat_meeting_unknown"] += 1
            continue
        meeting = (
            hasher("meeting", meeting_ids[0]) if meeting_ids else None,
            hasher("series", meeting_ids[1]) if meeting_ids and meeting_ids[1] else None,
        )
        if ex_engine.chat(c, meeting_hash=meeting[0], series_hash=meeting[1]).excluded:
            out.counts["chat_excluded"] += 1
            continue
        chat_hash = hasher("chat", c.id)
        msgs: list[ChatMessage] = sorted([m async for m in source.chat_messages(c.id)], key=lambda m: m.created_at)
        run: list[ChatMessage] = []
        for m in msgs:
            if not m.from_me:
                # A sender not on the roster has no address and can't be checked: left out.
                if ex_engine.people_reasons([m.sender], chat_hash=chat_hash):
                    out.counts["context_excluded"] += 1
                else:
                    run.append(m)
                continue
            await tick()
            ctx = run[-CONTEXT_MESSAGES:]
            await label_and_add(
                "chat",
                f"{c.id}:{m.id}",  # chat message IDs are unique only within their chat
                chat_hash,
                list(c.members),
                [x.sender for x in ctx],
                m.created_at,
                c.topic,
                m.text,
                "\n".join(x.text for x in ctx) or None,
                meeting=meeting,
                ref=c.id,
            )
            run = []
    await beat()
    return out


# --- persist --------------------------------------------------------------------------------
def held_out(item_hash: str) -> bool:
    return int(item_hash[:4], 16) % 100 < HELD_OUT_PERCENT


async def persist(
    engine: AsyncEngine, vault: Vault, ref: UserRef, kind: str, run_id: str, items: list[Item], version: int
) -> None:
    t, u = ref.tenant_id, ref.user_id
    async with user_tx(engine, ref) as conn:
        await lock_user_controls(conn, ref)
        status = (
            await conn.execute(
                text("select status from vanimo.learning_runs where id = :id for update"), {"id": run_id}
            )
        ).scalar_one_or_none()
        if status != "running":
            raise RunCancelled()  # "delete what was learned" (or the sweeper) won: store nothing
        if await controls_version(conn) != version:
            raise ControlsChanged()
        matcher = await load_matcher(conn, vault, ref)
        await conn.execute(text("delete from vanimo.l1_items where source_kind = :k"), {"k": kind})
        rows = []
        tokens: dict[str, tuple[str, str]] = {}
        for it in items:
            for red in (it.text, it.context, it.subject):
                if red is not None:
                    tokens.update(red.tokens)
            rows.append(
                {
                    "t": t,
                    "u": u,
                    "k": kind,
                    "run": run_id,
                    "ch": it.channel,
                    "ih": it.item_hash,
                    "th": it.thread_hash,
                    "mh": it.meeting_hash,
                    "sh": it.series_hash,
                    "people": json.dumps([{"p": p, "d": d} for p, d in it.people]),
                    "at": it.sent_at,
                    "subj": vault.encrypt_user(t, u, it.subject.text if it.subject else None, "l1_subject"),
                    "txt": vault.encrypt_user(t, u, it.text.text, "l1_text"),
                    "ctx": vault.encrypt_user(t, u, it.context.text if it.context else None, "l1_context"),
                    "rel": it.relationship,
                    "intent": it.intent,
                    "lang": it.language,
                    "wc": it.word_count,
                    # Retrieval looks up past replies by what they replied to (the same text a
                    # draft request will carry), falling back to the subject.
                    "vec": embed(it.context.text if it.context else it.subject.text if it.subject else ""),
                    "sus": it.text.suspicious or bool(it.context and it.context.suspicious),
                    "held": held_out(it.item_hash),
                }
            )
        if rows:
            await conn.execute(
                text(
                    "insert into vanimo.l1_items (tenant_id, owner_user_id, source_kind, run_id, channel, item_hash, "
                    "thread_hash, meeting_hash, series_hash, people, sent_at, subject_enc, text_enc, context_enc, "
                    "relationship, intent, language, word_count, vec, suspicious, held_out) values (:t, :u, :k, :run, "
                    ":ch, :ih, :th, :mh, :sh, cast(:people as jsonb), :at, :subj, :txt, :ctx, :rel, :intent, :lang, "
                    ":wc, cast(:vec as real[]), :sus, :held)"
                ),
                rows,
            )
        if tokens:
            await conn.execute(
                text(
                    "insert into vanimo.l1_tokens (tenant_id, owner_user_id, token, kind, value_enc) "
                    "values (:t, :u, :tok, :kind, :val) on conflict (owner_user_id, token) "
                    "do update set value_enc = excluded.value_enc"
                ),
                [
                    # A display value can itself hold a never-send word (a name): stored masked.
                    {
                        "t": t,
                        "u": u,
                        "tok": tok,
                        "kind": k,
                        "val": vault.encrypt_user(t, u, matcher.mask(v)[0], "l1_token"),
                    }
                    for tok, (k, v) in tokens.items()
                ],
            )
        # Tokens no stored item uses any more (people from conversations no longer learned).
        from vanimo.controls.jobs import gc_tokens

        await gc_tokens(conn, vault, ref)
