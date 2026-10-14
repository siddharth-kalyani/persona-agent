"""Persona store: style cards rebuilt from L1, the Persona Snapshot, and the user's studio
settings (architecture §9.2, MVP plan M2 "Persona Snapshot + basic studio")."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from vanimo.controls.neversend import Matcher
from vanimo.controls.store import load_matcher, lock_user_controls
from vanimo.db.session import UserRef, user_tx
from vanimo.learning import style
from vanimo.vault import Vault


@dataclass(frozen=True)
class StoredItem:
    id: str
    channel: str
    thread_hash: str
    subject: str | None
    text: str
    context: str | None
    relationship: str
    intent: str
    language: str
    word_count: int
    vec: list[float] | None
    held_out: bool
    suspicious: bool
    sent_at: Any


async def load_items(conn: AsyncConnection, vault: Vault, ref: UserRef, source_kind: str) -> list[StoredItem]:
    t, u = ref.tenant_id, ref.user_id
    rows = (
        await conn.execute(
            text(
                "select id, channel, thread_hash, subject_enc, text_enc, context_enc, relationship, intent, "
                "language, word_count, vec, held_out, suspicious, sent_at from vanimo.l1_items "
                "where source_kind = :k order by sent_at"
            ),
            {"k": source_kind},
        )
    ).all()
    return [
        StoredItem(
            id=str(r.id),
            channel=r.channel,
            thread_hash=r.thread_hash,
            subject=vault.decrypt_user(t, u, r.subject_enc, "l1_subject"),
            text=vault.decrypt_user(t, u, r.text_enc, "l1_text") or "",
            context=vault.decrypt_user(t, u, r.context_enc, "l1_context"),
            relationship=r.relationship,
            intent=r.intent,
            language=r.language,
            word_count=r.word_count,
            vec=list(r.vec) if r.vec is not None else None,
            held_out=r.held_out,
            suspicious=r.suspicious,
            sent_at=r.sent_at,
        )
        for r in rows
    ]


def examples(items: list[StoredItem], *, include_held_out: bool = True) -> list[style.Example]:
    return [
        style.Example(i.text, i.relationship, i.channel, i.language, i.intent, i.thread_hash)
        for i in items
        if include_held_out or not i.held_out
    ]


async def rebuild(engine: AsyncEngine, vault: Vault, ref: UserRef, source_kind: str) -> int:
    """Recompute every style card for the source from the stored L1 items. Returns cards written."""
    t, u = ref.tenant_id, ref.user_id
    async with user_tx(engine, ref) as conn:
        await lock_user_controls(conn, ref)
        items = await load_items(conn, vault, ref, source_kind)
        cards = style.build_cards(examples(items)) if items else {}
        await conn.execute(text("delete from vanimo.style_cards where source_kind = :k"), {"k": source_kind})
        if cards:
            await conn.execute(
                text(
                    "insert into vanimo.style_cards (tenant_id, owner_user_id, source_kind, slice, level, "
                    "example_count, card_enc) values (:t, :u, :k, :s, :l, :n, :c)"
                ),
                [
                    {
                        "t": t,
                        "u": u,
                        "k": source_kind,
                        "s": key,
                        "l": level,
                        "n": card["n"],
                        "c": vault.encrypt_user(t, u, json.dumps(card), "style_card"),
                    }
                    for key, (level, card) in cards.items()
                ],
            )
    return len(cards)


async def load_cards(conn: AsyncConnection, vault: Vault, ref: UserRef, source_kind: str) -> dict[str, dict[str, Any]]:
    rows = (
        await conn.execute(
            text("select slice, card_enc from vanimo.style_cards where source_kind = :k"), {"k": source_kind}
        )
    ).all()
    return {
        r.slice: json.loads(vault.decrypt_user(ref.tenant_id, ref.user_id, r.card_enc, "style_card") or "{}")
        for r in rows
    }


# --- studio settings ---------------------------------------------------------------------------
class PersonaSettings(BaseModel):
    """What the user tells the persona directly. Offsets are relative to the learned style."""

    formality: int = Field(0, ge=-2, le=2)
    length: int = Field(0, ge=-2, le=2)
    warmth: int = Field(0, ge=-2, le=2)
    emoji: bool = False
    polish: str = Field("light", pattern="^(none|light)$")
    phrases_do: list[str] = Field(default_factory=list, max_length=20)
    phrases_dont: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("phrases_do", "phrases_dont")
    @classmethod
    def _phrases(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for p in v:
            p = " ".join(p.split())
            if not p:
                continue
            if len(p) > 80:
                raise ValueError("phrase too long (80 characters max)")
            if p.casefold() not in {x.casefold() for x in out}:
                out.append(p)
        return out


async def load_settings(conn: AsyncConnection, vault: Vault, ref: UserRef) -> PersonaSettings:
    enc = (await conn.execute(text("select settings_enc from vanimo.persona_settings"))).scalar_one_or_none()
    if not enc:
        return PersonaSettings()
    return PersonaSettings.model_validate_json(vault.decrypt_user(ref.tenant_id, ref.user_id, enc, "persona") or "{}")


def mask_settings(settings: PersonaSettings, matcher: Matcher) -> PersonaSettings:
    """Never-send words typed into the studio are stored masked too (they reach drafting prompts)."""
    return settings.model_copy(
        update={
            "phrases_do": [matcher.mask(p)[0] or "" for p in settings.phrases_do],
            "phrases_dont": [matcher.mask(p)[0] or "" for p in settings.phrases_dont],
        }
    )


async def save_settings(engine: AsyncEngine, vault: Vault, ref: UserRef, settings: PersonaSettings) -> PersonaSettings:
    t, u = ref.tenant_id, ref.user_id
    async with user_tx(engine, ref) as conn:
        await lock_user_controls(conn, ref)
        settings = mask_settings(settings, await load_matcher(conn, vault, ref))
        await conn.execute(
            text(
                "insert into vanimo.persona_settings (owner_user_id, tenant_id, settings_enc) values (:u, :t, :s) "
                "on conflict (owner_user_id) do update set settings_enc = excluded.settings_enc, updated_at = now()"
            ),
            {"u": u, "t": t, "s": vault.encrypt_user(t, u, settings.model_dump_json(), "persona")},
        )
    return settings


# --- snapshot ----------------------------------------------------------------------------------
RELATIONSHIPS = ("manager", "report", "peer", "external", "personal")


async def snapshot(engine: AsyncEngine, vault: Vault, ref: UserRef, source_kind: str) -> dict[str, Any]:
    """The Persona Snapshot: overall style, per-relationship differences, the user's settings and
    how much was learned from where. Content-free except the user's own phrase habits."""
    async with user_tx(engine, ref) as conn:
        cards = await load_cards(conn, vault, ref, source_kind)
        settings = await load_settings(conn, vault, ref)
        counts = (
            await conn.execute(
                text(
                    "select channel, relationship, language, count(*) as n from vanimo.l1_items "
                    "where source_kind = :k group by channel, relationship, language"
                ),
                {"k": source_kind},
            )
        ).all()
        evals = (
            await conn.execute(
                text(
                    "select metrics, created_at from vanimo.eval_runs where source_kind = :k "
                    "order by created_at desc limit 1"
                ),
                {"k": source_kind},
            )
        ).first()
    by: dict[str, dict[str, int]] = {"channel": {}, "relationship": {}, "language": {}}
    total = 0
    for r in counts:
        total += r.n
        for dim in by:
            by[dim][getattr(r, dim)] = by[dim].get(getattr(r, dim), 0) + r.n
    audiences = []
    for rel in RELATIONSHIPS:
        found = style.lookup(cards, rel, "*")
        if found and found[0] == style.slice_key(rel):
            audiences.append({"relationship": rel, "card": found[1]})
    return {
        "source": source_kind,
        "learned_items": total,
        "by": by,
        "overall": cards.get(style.slice_key()),
        "audiences": audiences,
        "cards": len(cards),
        "settings": settings.model_dump(),
        "evaluation": {"metrics": evals.metrics, "at": evals.created_at.isoformat()} if evals else None,
    }
