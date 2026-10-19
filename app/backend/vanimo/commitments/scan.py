"""The incremental "new promises" scan: what the user sent since the last scan (MVP plan M5).

There is no background Graph token yet (no refresh tokens, no webhooks), so this runs when the user
opens the Commitments tab, like M4's matching. The order is the learner's (§6.5 X2):

  1. the onboarding gate for this source;
  2. Sent Items headers and chat rosters only (metadata) → the exclusion engine decides; a meeting
     chat whose meeting isn't in the calendar window isn't read (fail-closed);
  3. only then the user's own allowed messages since the last scan are read, at most
     `MAX_PER_SCAN` per call, oldest first, and redacted to L1 in memory;
  4. promises are found in L1 and stored under the controls lock if the controls didn't change.

Nothing but the promise (L1) and its lineage is stored; the message text isn't.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from vanimo.commitments import store
from vanimo.commitments.extract import Extractor, OfflineExtractor
from vanimo.controls.scan import CALENDAR_AHEAD, CALENDAR_BACK, meeting_links
from vanimo.controls.store import hasher_for, load_engine, load_matcher
from vanimo.db.session import UserRef, user_tx
from vanimo.drafting.context import build_redactor
from vanimo.gates import require_review_done
from vanimo.learning import labels
from vanimo.learning.backfill import controls_version
from vanimo.logs import get_logger
from vanimo.redaction.parse import strip_quotes, strip_signature_noise
from vanimo.redaction.pipeline import BackstopUnavailable, RedactionBlocked
from vanimo.sources.base import Address, WorkspaceSource
from vanimo.state import AppState

log = get_logger("vanimo.commitments")

FIRST_SCAN = timedelta(days=7)  # with no learning run yet: the last week only
MAX_PER_SCAN = 60  # messages read per call; the rest wait for the next one
MAX_CHATS = 200  # chats asked for new messages per call (Graph can't tell which chats are quiet)
MIN_INTERVAL_S = 60.0
MAX_CHARS = 8000


def extractor_for(state: AppState) -> Extractor:
    if state.settings.drafter == "bedrock":
        from vanimo.commitments.model import BedrockExtractor

        return BedrockExtractor(state.llm, state.router)
    return OfflineExtractor()


@dataclass
class ScanResult:
    found: int = 0
    hints: int = 0
    read: int = 0
    excluded: int = 0
    pending: bool = False  # more to read than one call reads
    skipped: bool = False  # throttled: scanned less than a minute ago
    counts: dict[str, int] = field(default_factory=dict)


class ScanThrottle:
    """At most one scan a minute per user (in-process: one API task in the MVP)."""

    def __init__(self) -> None:
        self._last: dict[str, float] = {}

    def release(self, key: str) -> None:
        """A scan stopped by an outage (F11 backstops) doesn't count: the retry may run at once."""
        self._last.pop(key, None)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        if now - self._last.get(key, -1e9) < MIN_INTERVAL_S:
            return False
        if len(self._last) > 10_000:
            self._last.clear()
        self._last[key] = now
        return True


THROTTLE = ScanThrottle()


@dataclass
class _Pending:
    at: datetime
    channel: str
    id: str
    thread_ref: str
    audience: list[Address]
    meeting: tuple[str | None, str | None] = (None, None)
    text: str | None = None  # chat messages arrive with their text; email bodies are read later


async def scan(state: AppState, user: UserRef, source: WorkspaceSource, *, self_email: str) -> ScanResult:
    from vanimo.drafting.service import _known

    out = ScanResult()
    await require_review_done(state.engine, user, source.kind)  # before the throttle: a refused call doesn't count
    if not THROTTLE.allow(f"{user.user_id}:{source.kind}"):
        out.skipped = True
        return out
    now = datetime.now(UTC)
    me = self_email.lower()
    hasher = hasher_for(state.vault, user)
    sample = await source.org_domains() if source.kind == "sample" else frozenset()
    async with user_tx(state.engine, user) as conn:
        version = await controls_version(conn)
        ex_engine = await load_engine(conn, state.vault, user, self_email=me, extra_org_domains=sample)
        matcher = await load_matcher(conn, state.vault, user)
        _, known_people = await _known(conn, state, user)
        mark = (
            await conn.execute(
                text("select scanned_until from vanimo.commitment_scans where source_kind = :k"), {"k": source.kind}
            )
        ).scalar_one_or_none()
    since = max(mark or now - FIRST_SCAN, now - store.WINDOW)
    directory = await state.directory_cache.get((str(user.user_id), source.kind), source, me)

    # 1-2. Metadata first: allowed sent emails and the user's own chat messages since `since`.
    pending: list[_Pending] = []
    async for h in source.sent_headers(since=since):
        if h.sent_at <= since:
            continue
        if ex_engine.message(h).excluded:
            out.excluded += 1
            continue
        pending.append(_Pending(h.sent_at, "email", h.id, h.conversation_id, list(h.participants)))
    by_url = meeting_links([e async for e in source.events(now - CALENDAR_BACK, now + CALENDAR_AHEAD)])
    asked = 0
    async for c in source.chats():
        # Only a known last-message time says a chat is quiet; otherwise Graph is asked for messages
        # since the mark (filtered server-side), after the roster decided.
        if c.last_message_at is not None and c.last_message_at <= since:
            continue
        if asked >= MAX_CHATS:
            out.counts["chats_not_checked"] = out.counts.get("chats_not_checked", 0) + 1
            continue
        ids = by_url.get(c.join_url or "") if c.chat_type == "meeting" else None
        if c.chat_type == "meeting" and ids is None:
            out.excluded += 1
            continue
        meeting = (hasher("meeting", ids[0]) if ids else None, hasher("series", ids[1]) if ids and ids[1] else None)
        if ex_engine.chat(c, meeting_hash=meeting[0], series_hash=meeting[1]).excluded:
            out.excluded += 1
            continue
        asked += 1
        async for m in source.chat_messages(c.id, since=since):
            if m.from_me and m.created_at > since:
                pending.append(_Pending(m.created_at, "chat", m.id, c.id, list(c.members), meeting, m.text))
    pending.sort(key=lambda p: p.at)
    batch = pending
    if len(pending) > MAX_PER_SCAN:
        # Cut only between two different times, so the next call (which reads after `until`) never
        # skips a message sent at the same instant as the last one read here.
        edge = pending[MAX_PER_SCAN].at
        batch = [p for p in pending[:MAX_PER_SCAN] if p.at < edge] or [p for p in pending if p.at == edge]
    out.pending = len(pending) > len(batch)

    # 3. Only now the text of the allowed messages, redacted to L1 in memory.
    units: list[store.Unit] = []
    for p in batch:
        raw = p.text
        if p.channel == "email":
            msg = await source.message(p.id)
            raw = (msg.body if msg.quoted else strip_quotes(msg.body)[0]) if msg else None
        out.read += 1
        body = strip_signature_noise(raw or "").strip()[:MAX_CHARS]
        if not body:
            continue
        redactor = build_redactor(matcher, hasher, directory, p.audience, known_people)
        try:
            red = await redactor.redact(body)
        except BackstopUnavailable:
            raise  # stop: nothing is marked scanned, the next scan reads these again
        except RedactionBlocked as e:
            out.counts[f"blocked_{e.reason}"] = out.counts.get(f"blocked_{e.reason}", 0) + 1
            continue
        others = {a.email.lower(): a for a in p.audience if a.email and a.email.lower() != me}
        units.append(
            store.Unit(
                channel=p.channel,
                # Chat message IDs are unique only within their chat: the chat is part of the key.
                item_hash=hasher("item", f"email:{p.id}" if p.channel == "email" else f"chat:{p.thread_ref}:{p.id}"),
                thread_hash=hasher("thread" if p.channel == "email" else "chat", p.thread_ref),
                people=[(hasher("person", e), ex_engine.domain_hashes(a.domain)) for e, a in sorted(others.items())],
                relationship=labels.relationship(
                    list(others.values()),
                    manager=directory.manager,
                    reports=directory.reports,
                    org_domains=directory.org_domains | sample,
                ),
                sent_at=p.at,
                text=red.text,
                tokens=red.tokens,
                ref=p.thread_ref,
                meeting_hash=p.meeting[0],
                series_hash=p.meeting[1],
            )
        )

    # 4. Promises, stored only if the controls are as they were when this scan began.
    extractor = extractor_for(state)
    found = await store.find(
        units,
        extractor,
        state.settings.cell_config.zone,
        now,
        seen=await store.seen_items(state.engine, user),
        counts=out.counts,
    )
    until = batch[-1].at if out.pending and batch else now
    saved = await store.save(
        state.engine,
        state.vault,
        user,
        source.kind,
        found,
        units,
        version,
        extractor=extractor.kind,
        scanned_until=until,
    )
    if saved is None:
        out.counts["controls_changed"] = 1
        return out
    out.found, out.hints = saved.stored, saved.hints
    log.info("commitments.scanned", count=out.read, outcome=f"found_{out.found}")
    return out


def summary(result: ScanResult) -> dict[str, Any]:
    return {
        "found": result.found,
        "hints": result.hints,
        "read": result.read,
        "excluded": result.excluded,
        "pending": result.pending,
        "skipped": result.skipped,
    }
