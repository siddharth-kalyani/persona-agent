"""The commitments ledger: storing what was found, with lineage, under the controls lock.

Promises come from learned items (after a learning run) and from the incremental scan
(`vanimo/commitments/scan.py`). Either way the item already passed the exclusion engine and was
redacted to L1. Before storing, the user's controls version is re-checked under the same lock as
purges and scrubs (§6.5 X4): a rule or never-send word added meanwhile wins, and nothing is stored.

A promise keeps its key (the item's HMAC and its position in it), so finding it again never makes
a duplicate and never reopens one the user marked done or "not a promise".
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
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
from vanimo.redaction.marks import TOKEN
from vanimo.vault import Vault

log = get_logger("vanimo.commitments")

WINDOW = timedelta(days=60)  # promises older than this aren't worth a ledger entry


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


async def find(units: Iterable[Unit], extractor: Extractor, tz: ZoneInfo, now: datetime) -> list[Candidate]:
    out: list[Candidate] = []
    for u in units:
        if not wanted(u, now):
            continue
        for n, f in enumerate(await extractor.find(u.text, made_at=u.sent_at, tz=tz)):
            out.append(Candidate(u, n, f))
    return out


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
            row = await conn.execute(
                text(
                    "insert into vanimo.commitments (tenant_id, owner_user_id, source_kind, channel, item_hash, "
                    "ordinal, thread_hash, meeting_hash, series_hash, people, relationship, made_at, text_enc, "
                    "what_enc, due_at, due_phrase_enc, ref_enc, extractor) values (:t, :u, :k, :ch, :ih, :n, :th, "
                    ":mh, :sh, cast(:people as jsonb), :rel, :at, :txt, :what, :due, :phrase, :ref, :ex) "
                    "on conflict (owner_user_id, item_hash, ordinal) do nothing returning id"
                ),
                {
                    "t": t,
                    "u": u,
                    "k": source_kind,
                    "ch": unit.channel,
                    "ih": unit.item_hash,
                    "n": c.ordinal,
                    "th": unit.thread_hash,
                    "mh": unit.meeting_hash,
                    "sh": unit.series_hash,
                    "people": json.dumps([{"p": p, "d": d} for p, d in unit.people]),
                    "rel": unit.relationship,
                    "at": unit.sent_at,
                    "txt": vault.encrypt_user(t, u, f.sentence, "commitment_text"),
                    "what": vault.encrypt_user(t, u, f.what, "commitment_what"),
                    "due": f.due_at,
                    "phrase": vault.encrypt_user(t, u, f.due_phrase, "commitment_due"),
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
) -> Saved | None:
    """After a learning run: promises in the items it just stored (same lineage, same L1)."""
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
    found = await find(units, extractor, tz, now)
    return await save(
        engine, vault, ref, source_kind, found, units, version, extractor=extractor.kind, scanned_until=started_at
    )
