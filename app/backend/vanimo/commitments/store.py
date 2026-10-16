"""The commitments ledger: storing what was found, with lineage, under the controls lock.

Promises come from learned items (after a learning run) and from the incremental scan
(`vanimo/commitments/scan.py`). Either way the item already passed the exclusion engine and was
redacted to L1. Before storing, the user's controls version is re-checked under the same lock as
purges and scrubs (§6.5 X4): a rule or never-send word added meanwhile wins, and nothing is stored.

A promise's key is an HMAC of its item and its normalised sentence, so finding it again (even with
another extractor, or a model answering in another order) never makes a duplicate and never reopens
one the user marked done or "not a promise". A message that already has promises isn't looked at
again, and a learning run looks at most `MAX_PER_RUN` messages (each is a model call on Bedrock).
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from vanimo.commitments.extract import Extractor, Found, looks_done
from vanimo.controls.store import load_matcher, lock_user_controls
from vanimo.db.session import UserRef, user_tx
from vanimo.learning.backfill import controls_version
from vanimo.logs import get_logger
from vanimo.redaction.marks import L1_MARKS, TOKEN
from vanimo.vault import Vault

log = get_logger("vanimo.commitments")

WINDOW = timedelta(days=60)  # promises older than this aren't worth a ledger entry
MAX_PER_RUN = 200  # messages looked at per learning run, newest first
BEAT_EVERY = 20


@dataclass
class Unit:
    """One of the user's own messages, already allowed and redacted (L1)."""

    channel: str  # email | chat
    item_hash: str
    thread_hash: str  # the conversation (email) or chat
    people: list[tuple[str, list[str]]]
    relationship: str
    sent_at: datetime
    text: str  # L1
    tokens: dict[str, tuple[str, str]]
    ref: str | None  # conversation or chat ID (in memory; stored encrypted)
    meeting_hash: str | None = None
    series_hash: str | None = None


@dataclass
class Candidate:
    unit: Unit
    ordinal: int
    found: Found


@dataclass
class Saved:
    stored: int = 0
    hints: int = 0
    skipped: dict[str, int] = field(default_factory=dict)


def wanted(unit: Unit, now: datetime) -> bool:
    """Work promises from the last 60 days; personal mail isn't a work ledger."""
    return unit.relationship != "personal" and unit.sent_at >= now - WINDOW


async def _no_beat() -> None:
    return None


async def find(
    units: Iterable[Unit],
    extractor: Extractor,
    tz: ZoneInfo,
    now: datetime,
    *,
    seen: frozenset[str] = frozenset(),
    limit: int | None = None,
    counts: dict[str, int] | None = None,
    beat: Callable[[], Awaitable[None]] = _no_beat,
) -> list[Candidate]:
    """Promises in the newest wanted units. A unit that already has promises (`seen`) is skipped; one
    the extractor fails on is skipped and counted, never the whole batch."""
    counts = counts if counts is not None else {}
    todo = sorted((u for u in units if wanted(u, now) and u.item_hash not in seen), key=lambda u: u.sent_at)
    if limit is not None and len(todo) > limit:
        counts["over_limit"] = len(todo) - limit
        todo = todo[-limit:]
    out: list[Candidate] = []
    for i, u in enumerate(todo, 1):
        try:
            found = await extractor.find(u.text, made_at=u.sent_at, tz=tz)
        except Exception as exc:
            counts["extract_failed"] = counts.get("extract_failed", 0) + 1
            log.warning("commitments.extract_failed", error_type=type(exc).__name__)
            continue
        out += [Candidate(u, n, f) for n, f in enumerate(found)]
        if i % BEAT_EVERY == 0:
            await beat()
    return out


async def seen_items(engine: AsyncEngine, ref: UserRef) -> frozenset[str]:
    async with user_tx(engine, ref) as conn:
        return frozenset((await conn.execute(text("select distinct item_hash from vanimo.commitments"))).scalars())


def _norm(sentence: str) -> str:
    return re.sub(r"\s+", " ", sentence).strip(" .!").lower()


def _tokens_in(c: Candidate) -> dict[str, tuple[str, str]]:
    used = set(TOKEN.findall(c.found.sentence)) | set(TOKEN.findall(c.found.what))
    return {t: v for t, v in c.unit.tokens.items() if t in used}


async def save(
    engine: AsyncEngine,
    vault: Vault,
    ref: UserRef,
    source_kind: str,
    candidates: Sequence[Candidate],
    later: Sequence[Unit],
    version: int,
    *,
    extractor: str,
    scanned_until: datetime | None,
) -> Saved | None:
    """Stores new promises and "looks done" hints. None if the user's controls changed meanwhile."""
    t, u = ref.tenant_id, ref.user_id
    out = Saved()
    async with user_tx(engine, ref) as conn:
        await lock_user_controls(conn, ref)
        if await controls_version(conn) != version:
            return None
        matcher = await load_matcher(conn, vault, ref)
        tokens: dict[str, tuple[str, str]] = {}
        for c in candidates:
            f, unit = c.found, c.unit

            def m(value: str | None) -> str | None:
                # Never-send words as they are now, also in what a model wrote (the output gate's rule).
                return matcher.mask(value, opaque=L1_MARKS)[0] if value else value

            row = await conn.execute(
                text(
                    "insert into vanimo.commitments (tenant_id, owner_user_id, source_kind, channel, item_hash, "
                    "ordinal, promise_hash, thread_hash, meeting_hash, series_hash, people, relationship, made_at, "
                    "text_enc, what_enc, due_at, due_phrase_enc, ref_enc, extractor) values (:t, :u, :k, :ch, :ih, "
                    ":n, :ph, :th, :mh, :sh, cast(:people as jsonb), :rel, :at, :txt, :what, :due, :phrase, :ref, "
                    ":ex) on conflict (owner_user_id, promise_hash) do nothing returning id"
                ),
                {
                    "t": t,
                    "u": u,
                    "k": source_kind,
                    "ch": unit.channel,
                    "ih": unit.item_hash,
                    "n": min(c.ordinal, 20),
                    "ph": vault.key_hash(t, "promise", f"{unit.item_hash}:{_norm(f.sentence)}"),
                    "th": unit.thread_hash,
                    "mh": unit.meeting_hash,
                    "sh": unit.series_hash,
                    "people": json.dumps([{"p": p, "d": d} for p, d in unit.people]),
                    "rel": unit.relationship,
                    "at": unit.sent_at,
                    "txt": vault.encrypt_user(t, u, m(f.sentence), "commitment_text"),
                    "what": vault.encrypt_user(t, u, m(f.what), "commitment_what"),
                    "due": f.due_at,
                    "phrase": vault.encrypt_user(t, u, m(f.due_phrase), "commitment_due"),
                    "ref": vault.encrypt_user(t, u, unit.ref, "commitment_ref"),
                    "ex": extractor,
                },
            )
            if row.first():
                out.stored += 1
                tokens |= _tokens_in(c)
        if tokens:
            # The owner's display values for the names in a promise (masked like learned tokens).
            await conn.execute(
                text(
                    "insert into vanimo.l1_tokens (tenant_id, owner_user_id, token, kind, value_enc) "
                    "values (:t, :u, :tok, :kind, :val) on conflict (owner_user_id, token) do nothing"
                ),
                [
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
        out.hints = await _hints(conn, vault, ref, later)
        if scanned_until is not None:
            await conn.execute(
                text(
                    "insert into vanimo.commitment_scans (owner_user_id, tenant_id, source_kind, scanned_until) "
                    "values (:u, :t, :k, :s) on conflict (owner_user_id, source_kind) do update "
                    "set scanned_until = greatest(vanimo.commitment_scans.scanned_until, excluded.scanned_until), "
                    "updated_at = now()"
                ),
                {"u": u, "t": t, "k": source_kind, "s": scanned_until},
            )
    return out


async def _hints(conn: AsyncConnection, vault: Vault, ref: UserRef, later: Sequence[Unit]) -> int:
    """Open promises a later message of the user's in the same thread or chat seems to deliver."""
    if not later:
        return 0
    threads = sorted({x.thread_hash for x in later})
    rows = (
        await conn.execute(
            text(
                "select id, thread_hash, made_at, what_enc from vanimo.commitments "
                "where status = 'open' and done_hint_at is null and thread_hash = any(:th)"
            ),
            {"th": threads},
        )
    ).all()
    hinted = 0
    for r in rows:
        what = vault.decrypt_user(ref.tenant_id, ref.user_id, r.what_enc, "commitment_what") or ""
        after = sorted(
            (x for x in later if x.thread_hash == r.thread_hash and x.sent_at > r.made_at), key=lambda x: x.sent_at
        )
        hit = next((x for x in after if looks_done(what, x.text)), None)
        if hit:
            await conn.execute(
                text("update vanimo.commitments set done_hint_at = :at where id = :id"), {"at": hit.sent_at, "id": r.id}
            )
            hinted += 1
    return hinted


async def from_learning(
    engine: AsyncEngine,
    vault: Vault,
    ref: UserRef,
    source_kind: str,
    items: Sequence[Any],
    version: int,
    extractor: Extractor,
    tz: ZoneInfo,
    started_at: datetime,
    beat: Callable[[], Awaitable[None]] = _no_beat,
) -> Saved | None:
    """After a learning run: promises in the items it just stored (same lineage, same L1). Messages
    that already have promises aren't looked at again; at most `MAX_PER_RUN`, newest first."""
    units = [
        Unit(
            channel=i.channel,
            item_hash=i.item_hash,
            thread_hash=i.thread_hash,
            people=i.people,
            relationship=i.relationship,
            sent_at=i.sent_at,
            text=i.text.text,
            tokens=i.text.tokens,
            ref=i.ref,
            meeting_hash=i.meeting_hash,
            series_hash=i.series_hash,
        )
        for i in items
    ]
    now = datetime.now(UTC)
    counts: dict[str, int] = {}
    found = await find(
        units, extractor, tz, now, seen=await seen_items(engine, ref), limit=MAX_PER_RUN, counts=counts, beat=beat
    )
    return await save(
        engine, vault, ref, source_kind, found, units, version, extractor=extractor.kind, scanned_until=started_at
    )
