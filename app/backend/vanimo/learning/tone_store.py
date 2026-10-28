"""Conversation tones in the database (F15): what learning judged, what drafting judged live for a new
conversation, and the user's own choice, which always wins and survives learning again.

Rows hold hashes and labels only. Names are looked up in the Sources index (people and chats, already
encrypted and scrubbed) when the owner's Persona page shows them.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from vanimo.controls.neversend import render_removed
from vanimo.db.session import UserRef
from vanimo.learning.tones import RANK, Judged, Tone, most_formal
from vanimo.vault import Vault


@dataclass(frozen=True)
class ToneRow:
    bucket: str
    key: str  # person hash (email, dm) or chat hash (group)
    people: Sequence[tuple[str, Sequence[str]]]  # lineage: (person hash, domain hashes)
    chat: str | None  # the 1:1 or group chat it was learned in
    judged: Judged


@dataclass(frozen=True)
class Known:
    tone: Tone  # the effective tone: the user's choice, else the judged one
    judged: Tone
    override: Tone | None
    basis: str
    judged_by: str


def _row_params(ref: UserRef, source_kind: str, r: ToneRow) -> dict[str, Any]:
    return {
        "t": ref.tenant_id,
        "u": ref.user_id,
        "k": source_kind,
        "b": r.bucket,
        "key": r.key,
        "people": json.dumps([{"p": p, "d": list(d)} for p, d in r.people]),
        "chat": r.chat,
        "tone": r.judged.tone,
        "basis": r.judged.basis,
        "by": r.judged.judged_by,
        "mine": r.judged.mine,
        "theirs": r.judged.theirs,
    }


_UPSERT = (
    "insert into vanimo.conversation_tones (tenant_id, owner_user_id, source_kind, bucket, key_hash, people, "
    "chat_hash, tone, basis, judged_by, mine, theirs) values (:t, :u, :k, :b, :key, cast(:people as jsonb), :chat, "
    ":tone, :basis, :by, :mine, :theirs) on conflict (owner_user_id, source_kind, bucket, key_hash) do update set "
    "people = excluded.people, chat_hash = excluded.chat_hash, tone = excluded.tone, basis = excluded.basis, "
    "judged_by = excluded.judged_by, mine = excluded.mine, theirs = excluded.theirs, updated_at = now()"
)


async def replace(conn: AsyncConnection, ref: UserRef, source_kind: str, rows: Sequence[ToneRow]) -> None:
    """After learning: every judged conversation, keeping the user's choices. A conversation no longer
    learned goes, unless the user chose its tone (their choice is a setting: it stays)."""
    keys = [f"{r.bucket}:{r.key}" for r in rows]
    await conn.execute(
        text(
            "delete from vanimo.conversation_tones where source_kind = :k and override is null "
            "and not (bucket || ':' || key_hash = any(:keys))"
        ),
        {"k": source_kind, "keys": keys},
    )
    if rows:
        await conn.execute(text(_UPSERT), [_row_params(ref, source_kind, r) for r in rows])


async def save_one(conn: AsyncConnection, ref: UserRef, source_kind: str, row: ToneRow) -> None:
    """A tone judged while drafting in a conversation learning never saw (a new chat, a new contact)."""
    await conn.execute(text(_UPSERT), _row_params(ref, source_kind, row))


async def overrides(conn: AsyncConnection, source_kind: str) -> dict[tuple[str, str], Tone]:
    rows = (
        await conn.execute(
            text(
                "select bucket, key_hash, override from vanimo.conversation_tones "
                "where source_kind = :k and override is not null"
            ),
            {"k": source_kind},
        )
    ).all()
    return {(r.bucket, r.key_hash): r.override for r in rows}


async def known(conn: AsyncConnection, source_kind: str, bucket: str, keys: Sequence[str]) -> dict[str, Known]:
    if not keys:
        return {}
    rows = (
        await conn.execute(
            text(
                "select key_hash, tone, override, basis, judged_by from vanimo.conversation_tones "
                "where source_kind = :k and bucket = :b and key_hash = any(:keys)"
            ),
            {"k": source_kind, "b": bucket, "keys": list(keys)},
        )
    ).all()
    return {r.key_hash: Known(r.override or r.tone, r.tone, r.override, r.basis, r.judged_by) for r in rows}


def email_tone(found: dict[str, Known], keys: Sequence[str]) -> Tone | None:
    """An email to several people is written for the most formal of them (a casual friend with the manager
    in copy still gets the formal email)."""
    return most_formal([found[k].tone for k in keys if k in found])


async def set_override(conn: AsyncConnection, source_kind: str, bucket: str, key: str, tone: Tone | None) -> bool:
    """The user's choice for one conversation (None: back to what Vanimo judged). False if it doesn't exist."""
    result = await conn.execute(
        text(
            "update vanimo.conversation_tones set override = :o, updated_at = now() "
            "where source_kind = :k and bucket = :b and key_hash = :key"
        ),
        {"o": tone, "k": source_kind, "b": bucket, "key": key},
    )
    return result.rowcount > 0


async def listed(conn: AsyncConnection, vault: Vault, ref: UserRef, source_kind: str) -> list[dict[str, Any]]:
    """Every conversation with its tone, for the owner's Persona page: names from the Sources index."""
    t, u = ref.tenant_id, ref.user_id
    rows = (
        await conn.execute(
            text(
                "select bucket, key_hash, tone, override, basis, judged_by, mine, theirs, updated_at "
                "from vanimo.conversation_tones where source_kind = :k"
            ),
            {"k": source_kind},
        )
    ).all()
    people = {
        r.key_hash: r
        for r in (await conn.execute(text("select key_hash, email_enc, name_enc from vanimo.source_people"))).all()
    }
    chats = {
        r.key_hash: r
        for r in (
            await conn.execute(text("select key_hash, chat_type, label_enc, member_count from vanimo.source_chats"))
        ).all()
    }
    learned = {
        r.counterpart: r.n
        for r in (
            await conn.execute(
                text(
                    "select counterpart, count(*) as n from vanimo.l1_items where source_kind = :k "
                    "and counterpart is not null group by counterpart"
                ),
                {"k": source_kind},
            )
        ).all()
    }
    out = []
    for r in rows:
        label, email, members = None, None, None
        if r.bucket == "group" and r.key_hash in chats:
            c = chats[r.key_hash]
            label = render_removed(vault.decrypt_user(t, u, c.label_enc, "chat_label"))
            members = c.member_count
        elif r.key_hash in people:
            p = people[r.key_hash]
            email = vault.decrypt_user(t, u, p.email_enc, "email")
            label = render_removed(vault.decrypt_user(t, u, p.name_enc, "name")) or email
        out.append(
            {
                "key": r.key_hash,
                "bucket": r.bucket,
                "tone": r.override or r.tone,
                "judged": r.tone,
                "override": r.override,
                "basis": r.basis,
                "judgedBy": r.judged_by,
                "mine": r.mine,
                "theirs": r.theirs,
                "label": label,
                "email": email,
                "members": members,
                "learned": learned.get(r.key_hash, 0),
                "updatedAt": r.updated_at.isoformat(),
            }
        )
    out.sort(key=lambda c: (-RANK[c["tone"]], -(c["mine"] + c["theirs"]), (c["label"] or "").lower()))
    return out
