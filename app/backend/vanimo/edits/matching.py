"""Draft ↔ sent matching (architecture §9.2: "the only reliable signal", research R05 §7.7).

For every stored draft still pending, look at the user's recent **sent** mail:
  * a reply draft matches the first message the user sent in the same conversation after it; if
    several drafts were made in that conversation, the latest one before the send is matched and
    the older ones are marked superseded (one sent message is one observation, never three);
  * a new-email draft matches a sent message to any of the same people that shares enough text;
    messages already compared and rejected, or claimed by another draft, are skipped;
  * within 72 hours, otherwise the draft is marked unmatched (discarded) — but only once every
    candidate was actually examined (the per-sync read budget never decides it).
Headers first: the exclusion engine decides on the sent message before its text is read
(two-phase, §6.5 X2); an excluded one ends the draft's tracking. The sent text is redacted to L1
in memory and compared with the draft's L1. Stored: the outcome, the edit kinds, the rules'
evidence, an HMAC of the sent message, and the sent message's participants added to the draft's
lineage (so excluding anyone on the real reply purges the evidence too) — never the sent text.
Everything is written under the controls lock, and only if the user's controls didn't change
since the sync began (§6.5 X4).

Teams chat drafts (M5) match the first message the user posted in the same chat after the draft,
the same way: the chat's roster is decided on first, then only the user's own messages since the
oldest pending draft are read. Edits to chat drafts teach only channel-neutral rules (phrases,
word swaps, exclamation marks): greeting, sign-off and length are email habits.

The sample workspace has no new sent mail, so its "Mark as sent" action feeds the user's edited
text through the same path (`record_sent`).
"""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from vanimo.controls.neversend import Matcher, Term
from vanimo.controls.store import hasher_for, load_engine, load_terms, lock_user_controls
from vanimo.db.session import UserRef, user_tx
from vanimo.drafting.context import DraftError, build_redactor
from vanimo.edits import rules
from vanimo.edits.diff import REWRITE_SIMILARITY, Comparison, compare, similarity
from vanimo.learning.backfill import controls_version
from vanimo.logs import get_logger
from vanimo.redaction.parse import strip_quotes, strip_signature_noise
from vanimo.redaction.pipeline import RedactionBlocked
from vanimo.sources.base import Address, SentHeader, WorkspaceSource
from vanimo.state import AppState

log = get_logger("vanimo.edits")

MATCH_WINDOW = timedelta(hours=72)
RECENT_SENT = 50
MAX_FETCHES = 10  # sent bodies read per sync (denial of wallet, Graph throttling)
MAX_CANDIDATES = 5
EMAIL_ONLY_EDITS = frozenset({"greeting", "sign_off", "length"})  # never learned from a chat


def _for_channel(comparison: Comparison, channel: str) -> Comparison:
    if channel != "chat":
        return comparison
    return dataclasses.replace(comparison, edits=[e for e in comparison.edits if e.kind not in EMAIL_ONLY_EDITS])


async def _context(state: AppState, user: UserRef, source: WorkspaceSource, self_email: str) -> dict[str, Any]:
    from vanimo.drafting.service import _known, _sample_domains

    async with user_tx(state.engine, user) as conn:
        engine = await load_engine(
            conn, state.vault, user, self_email=self_email, extra_org_domains=_sample_domains(source)
        )
        terms = await load_terms(conn, state.vault, user)
        _, known_people = await _known(conn, state, user)
        version = await controls_version(conn)
    directory = await state.directory_cache.get((str(user.user_id), source.kind), source, self_email)
    matcher = Matcher([Term(t["term_id"], t["text"], t["kind"], tuple(t["variants"]), t["folds"]) for t in terms])
    return {
        "engine": engine,
        "matcher": matcher,
        "known_people": known_people,
        "directory": directory,
        "hasher": hasher_for(state.vault, user),
        "version": version,
    }


def _to_l1(ctx: dict[str, Any], body: str, people: list[Address]) -> str | None:
    redactor = build_redactor(ctx["matcher"], ctx["hasher"], ctx["directory"], people, ctx["known_people"])
    try:
        return redactor.redact(strip_signature_noise(strip_quotes(body)[0])[:8000]).text
    except RedactionBlocked:
        return None


def _lineage(ctx: dict[str, Any], people: list[Address], me: str) -> list[dict[str, Any]]:
    engine, hasher = ctx["engine"], ctx["hasher"]
    uniq = {a.email.lower(): a for a in people if a.email and a.email.lower() != me}
    return [{"p": hasher("person", e), "d": engine.domain_hashes(a.domain)} for e, a in sorted(uniq.items())]


async def _store_match(
    state: AppState,
    user: UserRef,
    ctx: dict[str, Any],
    draft: Any,
    comparison: Comparison,
    source_kind: str,
    *,
    sent_hash: str | None,
    sent_people: list[dict[str, Any]],
) -> str:
    """Record the outcome under the controls lock. Returns "recorded", "changed" (controls changed
    since the sync began: try again next time) or "gone" (deleted or matched meanwhile)."""
    async with user_tx(state.engine, user) as conn:
        await lock_user_controls(conn, user)
        if await controls_version(conn) != ctx["version"]:
            return "changed"
        alive = (
            await conn.execute(
                text("select people from vanimo.drafts where id = :id and match_state = 'pending' for update"),
                {"id": draft.id},
            )
        ).first()
        if alive is None:
            return "gone"
        if (
            sent_hash
            and (
                await conn.execute(text("select 1 from vanimo.edit_events where sent_hash = :h"), {"h": sent_hash})
            ).first()
        ):
            return "gone"  # this sent message already counted for another draft
        known = {p["p"] for p in alive.people}
        people = list(alive.people) + [p for p in sent_people if p["p"] not in known]
        await conn.execute(
            text("update vanimo.drafts set match_state = 'matched', people = cast(:p as jsonb) where id = :id"),
            {"p": json.dumps(people), "id": draft.id},
        )
        event_id = await rules.record(
            conn,
            state.vault,
            user,
            ctx["hasher"],
            draft_id=str(draft.id),
            source_kind=source_kind,
            relationship=draft.relationship,
            comparison=_for_channel(comparison, getattr(draft, "channel", "email")),
        )
        if sent_hash:
            await conn.execute(
                text("update vanimo.edit_events set sent_hash = :h where id = :id"), {"h": sent_hash, "id": event_id}
            )
    return "recorded"


async def _pending(state: AppState, user: UserRef, source_kind: str) -> list[Any]:
    async with user_tx(state.engine, user) as conn:
        return list(
            (
                await conn.execute(
                    text(
                        "select id, mode, channel, thread_hash, meeting_hash, series_hash, people, text_enc, "
                        "created_at, relationship, checked_sent, chat_ref_enc "
                        "from vanimo.drafts where match_state = 'pending' and source_kind = :k order by created_at"
                    ),
                    {"k": source_kind},
                )
            ).all()
        )


async def _set_state(state: AppState, user: UserRef, ids: list[Any], new_state: str) -> None:
    if not ids:
        return
    async with user_tx(state.engine, user) as conn:
        await conn.execute(
            text("update vanimo.drafts set match_state = :s where id = any(:ids) and match_state = 'pending'"),
            {"s": new_state, "ids": ids},
        )


async def sync(state: AppState, user: UserRef, source: WorkspaceSource, *, self_email: str) -> dict[str, int]:
    """Match pending drafts to recent sent mail. Returns content-free counts."""
    counts = {"matched": 0, "unmatched": 0, "excluded": 0, "superseded": 0, "pending": 0}
    everything = await _pending(state, user, source.kind)
    if not everything:
        return counts
    pending = [d for d in everything if d.channel == "email"]
    chats = [d for d in everything if d.channel == "chat"]
    ctx = await _context(state, user, source, self_email)
    hasher, me = ctx["hasher"], self_email.lower()
    async with user_tx(state.engine, user) as conn:
        claimed = set(
            (await conn.execute(text("select sent_hash from vanimo.edit_events where sent_hash is not null")))
            .scalars()
            .all()
        )
    now = datetime.now(UTC)
    sent: list[SentHeader] = sorted(await source.recent_sent(RECENT_SENT), key=lambda h: h.sent_at)
    bodies: dict[str, str | None] = {}
    fetches = 0
    done: set[Any] = set()
    deferred: set[Any] = set()  # a candidate wasn't read (budget): never marked unmatched this time

    async def body_of(h: SentHeader) -> str | None:
        nonlocal fetches
        if h.id not in bodies:
            fetches += 1
            m = await source.message(h.id)
            bodies[h.id] = m.body if m else None
        return bodies[h.id]

    # Reply drafts: each sent reply in a conversation claims the latest draft made before it.
    for h in sent:
        sh = hasher("sent", h.id)
        if sh in claimed:
            continue
        th = hasher("thread", h.conversation_id)
        drafts = [
            d
            for d in pending
            if d.id not in done and d.mode == "reply" and d.thread_hash == th
            and d.created_at <= h.sent_at <= d.created_at + MATCH_WINDOW
        ]  # fmt: skip
        if not drafts:
            continue
        latest, older = drafts[-1], [d.id for d in drafts[:-1]]
        if ctx["engine"].message(h).excluded:
            await _set_state(state, user, [d.id for d in drafts], "excluded")  # never read
            done.update(d.id for d in drafts)
            counts["excluded"] += len(drafts)
            continue
        if fetches >= MAX_FETCHES and h.id not in bodies:
            deferred.update(d.id for d in drafts)
            continue  # budget spent: these stay pending for the next sync
        result = await _try(state, user, ctx, source, latest, h, await body_of(h), sh, me)
        if result == "recorded":
            claimed.add(sh)
            counts["matched"] += 1
            await _set_state(state, user, older, "superseded")
            counts["superseded"] += len(older)
            done.update([latest.id, *older])
        elif result == "changed":
            return counts  # controls changed: start again next time with the new rules

    # New-email drafts: a sent message to the same people with enough text in common.
    for d in pending:
        if d.id in done or d.mode != "new":
            continue
        draft_people = {p["p"] for p in d.people}
        checked = set(d.checked_sent)
        window_end = d.created_at + MATCH_WINDOW
        candidates = [
            h
            for h in sent
            if d.created_at <= h.sent_at <= window_end
            and hasher("sent", h.id) not in claimed
            and hasher("sent", h.id) not in checked
            and draft_people & {hasher("person", a.email.lower()) for a in h.recipients}
        ][:MAX_CANDIDATES]
        examined_all = True
        for h in candidates:
            if ctx["engine"].message(h).excluded:
                checked.add(hasher("sent", h.id))
                continue
            if fetches >= MAX_FETCHES and h.id not in bodies:
                examined_all = False
                break
            sh = hasher("sent", h.id)
            result = await _try(state, user, ctx, source, d, h, await body_of(h), sh, me, need_similarity=True)
            if result == "recorded":
                claimed.add(sh)
                counts["matched"] += 1
                done.add(d.id)
                break
            if result == "changed":
                return counts
            checked.add(sh)  # compared and not this draft: never read again for it
        if d.id not in done and checked != set(d.checked_sent):
            async with user_tx(state.engine, user) as conn:
                await conn.execute(
                    text("update vanimo.drafts set checked_sent = cast(:c as jsonb) where id = :id"),
                    {"c": json.dumps(sorted(checked)), "id": d.id},
                )
        if d.id not in done and examined_all and now > window_end:
            await _set_state(state, user, [d.id], "unmatched")
            counts["unmatched"] += 1
            done.add(d.id)

    # Reply drafts with no reply sent in their window.
    for d in pending:
        if d.id not in done and d.id not in deferred and d.mode == "reply" and now > d.created_at + MATCH_WINDOW:
            await _set_state(state, user, [d.id], "unmatched")
            counts["unmatched"] += 1
    if chats and await _sync_chats(state, user, ctx, source, chats, claimed, counts, me, now) == "changed":
        return counts
    counts["pending"] = len(everything) - sum(counts[k] for k in ("matched", "unmatched", "excluded", "superseded"))
    log.info("edits.sync", count=counts["matched"], outcome=f"unmatched_{counts['unmatched']}")
    return counts


async def _sync_chats(
    state: AppState,
    user: UserRef,
    ctx: dict[str, Any],
    source: WorkspaceSource,
    drafts: list[Any],
    claimed: set[str],
    counts: dict[str, int],
    me: str,
    now: datetime,
) -> str:
    """Teams drafts: in each chat, every message the user posted claims the latest draft made before
    it (older ones are superseded). The roster decides before any message is read."""
    hasher, engine = ctx["hasher"], ctx["engine"]
    t, u = user.tenant_id, user.user_id
    by_chat: dict[str, list[Any]] = {}
    for d in drafts:
        chat_id = state.vault.decrypt_user(t, u, d.chat_ref_enc, "draft_chat")
        if chat_id:
            by_chat.setdefault(chat_id, []).append(d)
    reads = 0
    for chat_id, group in by_chat.items():
        group.sort(key=lambda d: d.created_at)
        expired = [d.id for d in group if now > d.created_at + MATCH_WINDOW]
        if reads >= MAX_FETCHES:
            continue  # stay pending for the next sync
        chat = await source.chat(chat_id)
        meeting = (group[0].meeting_hash, group[0].series_hash)
        if chat is None or engine.chat(chat, meeting_hash=meeting[0], series_hash=meeting[1]).excluded:
            ids = [d.id for d in group]
            await _set_state(state, user, ids, "excluded" if chat else "unmatched")
            counts["excluded" if chat else "unmatched"] += len(ids)
            continue
        reads += 1
        since = group[0].created_at - timedelta(minutes=1)
        mine = sorted(
            [m async for m in source.chat_messages(chat_id, since=since) if m.from_me and m.created_at >= since],
            key=lambda m: m.created_at,
        )
        done: set[Any] = set()
        for m in mine:
            sh = hasher("sent", f"chat:{m.id}")
            if sh in claimed:
                continue
            open_drafts = [
                d for d in group
                if d.id not in done and d.created_at <= m.created_at <= d.created_at + MATCH_WINDOW
            ]  # fmt: skip
            if not open_drafts:
                continue
            latest, older = open_drafts[-1], [d.id for d in open_drafts[:-1]]
            sent_l1 = _chat_l1(ctx, m.text, list(chat.members))
            if sent_l1 is None:
                continue
            draft_l1 = state.vault.decrypt_user(t, u, latest.text_enc, "draft_text") or ""
            result = await _store_match(
                state,
                user,
                ctx,
                latest,
                compare(draft_l1, sent_l1),
                source.kind,
                sent_hash=sh,
                sent_people=_lineage(ctx, list(chat.members), me),
            )
            if result == "changed":
                return "changed"
            if result == "recorded":
                claimed.add(sh)
                counts["matched"] += 1
                await _set_state(state, user, older, "superseded")
                counts["superseded"] += len(older)
                done.update([latest.id, *older])
        stale = [i for i in expired if i not in done]
        await _set_state(state, user, stale, "unmatched")
        counts["unmatched"] += len(stale)
    return "ok"


def _chat_l1(ctx: dict[str, Any], body: str, people: list[Address]) -> str | None:
    redactor = build_redactor(ctx["matcher"], ctx["hasher"], ctx["directory"], people, ctx["known_people"])
    try:
        return redactor.redact(strip_signature_noise(body)[:8000]).text
    except RedactionBlocked:
        return None


async def _try(
    state: AppState,
    user: UserRef,
    ctx: dict[str, Any],
    source: WorkspaceSource,
    d: Any,
    h: SentHeader,
    body: str | None,
    sent_hash: str,
    me: str,
    *,
    need_similarity: bool = False,
) -> str:
    if body is None:
        return "skip"
    sent_l1 = _to_l1(ctx, body, list(h.participants))
    if sent_l1 is None:
        return "skip"
    draft_l1 = state.vault.decrypt_user(user.tenant_id, user.user_id, d.text_enc, "draft_text") or ""
    if need_similarity and similarity(draft_l1, sent_l1) < REWRITE_SIMILARITY:
        return "skip"  # a different email to the same person
    return await _store_match(
        state,
        user,
        ctx,
        d,
        compare(draft_l1, sent_l1),
        source.kind,
        sent_hash=sent_hash,
        sent_people=_lineage(ctx, list(h.participants), me),
    )


async def record_sent(
    state: AppState, user: UserRef, source: WorkspaceSource, *, self_email: str, draft_id: str, sent_text: str
) -> Comparison:
    """Sample workspace only: the user's final text stands in for the message they sent."""
    if source.kind != "sample":
        raise DraftError("sample_workspace_only", 404)
    async with user_tx(state.engine, user) as conn:
        d = (
            await conn.execute(
                text(
                    "select id, mode, channel, thread_hash, people, text_enc, created_at, relationship, match_state "
                    "from vanimo.drafts where id = :id and source_kind = 'sample'"
                ),
                {"id": draft_id},
            )
        ).first()
    if d is None:
        raise DraftError("not_found", 404)
    if d.match_state != "pending":
        raise DraftError("already_matched", 409)
    ctx = await _context(state, user, source, self_email)
    people = [Address(p.email or "", p.full_name) for p in ctx["known_people"] if p.email]
    sent_l1 = _chat_l1(ctx, sent_text, people) if d.channel == "chat" else _to_l1(ctx, sent_text, people)
    if sent_l1 is None:
        raise DraftError("text_blocked", 422)
    draft_l1 = state.vault.decrypt_user(user.tenant_id, user.user_id, d.text_enc, "draft_text") or ""
    comparison = compare(draft_l1, sent_l1)
    result = await _store_match(state, user, ctx, d, comparison, "sample", sent_hash=None, sent_people=[])
    if result == "changed":
        raise DraftError("controls_changed", 409)
    if result != "recorded":
        raise DraftError("already_matched", 409)
    return comparison
