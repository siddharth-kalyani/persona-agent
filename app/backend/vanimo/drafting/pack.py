"""The persona pack for one draft (architecture §9.2): the style card for this audience, the
user's studio settings and a few of their own past messages as examples.

Examples (exemplars):
  * every stored item is re-checked against the live exclusion rules first (§6.5 X5): a rule
    added a moment ago wins even before the purge job has deleted the item;
  * same scope — the same thread, or written to one of the same people — are given verbatim;
  * anything else only as a structure skeleton (greeting form, length, kind of message), so facts
    from one audience never reach another (cross-audience leakage, §10).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from vanimo.controls.engine import ExclusionEngine
from vanimo.db.session import UserRef
from vanimo.drafting.context import LiveContext
from vanimo.learning import style
from vanimo.learning.embed import cosine, embed
from vanimo.learning.persona import PersonaSettings, StoredItem, examples, load_cards, load_items, load_settings
from vanimo.redaction.marks import TOKEN
from vanimo.redaction.pipeline import Hasher
from vanimo.vault import Vault

MAX_EXEMPLARS = 3
MIN_SIMILARITY = 0.12

# Before anything is learned: a neutral card, clearly reported to the user as such.
DEFAULT_CARD: dict[str, Any] = {
    "n": 0,
    "greetings": [["Hi {first},", 1.0]],
    "sign_offs": [["Thanks,\n{me}", 1.0]],
    "length": {"median": 60, "p25": 35, "p75": 90},
    "formality": 0.5,
    "exclamation_rate": 0.1,
    "question_rate": 0.3,
    "emoji_rate": 0.0,
    "phrases": [],
    "keep_list": [],
    "languages": {},
    "intents": {},
}


@dataclass(frozen=True)
class Exemplar:
    text: str  # L1: the message itself (verbatim) or its skeleton
    verbatim: bool
    relationship: str
    why: str  # content-free: same_thread | same_people | similar


@dataclass
class PersonaPack:
    card_key: str | None
    card: dict[str, Any]
    overall: dict[str, Any] | None
    settings: PersonaSettings
    exemplars: list[Exemplar]
    stored_tokens: dict[str, str] = field(default_factory=dict)  # owner's values for tokens in exemplars
    excluded_items: int = 0  # items the live rules filtered out (logical exclusion before purge)

    @property
    def learned(self) -> bool:
        return self.card.get("n", 0) > 0


def skeleton(item: StoredItem) -> str:
    """The shape of a message without its content."""
    greeting = style.greeting_of(item.text)
    sign_off = style.sign_off_of(item.text)
    words = len(style._words(style.body_lines(item.text) or item.text))
    parts = [greeting or "(no greeting)", f"[{words} words: {item.intent}]", sign_off or "(no sign-off)"]
    return "\n".join(parts)


def _email_habits(
    card: dict[str, Any], card_key: str | None, items: list[StoredItem], relationship: str
) -> tuple[dict[str, Any], str | None]:
    """Greetings, sign-offs and length are habits of the channel: when the style card for this
    audience mixes in Teams chats (where nobody writes "Dear …"), take them from the user's emails —
    to this audience if there are enough, otherwise all of them. Tone and phrases stay with the card."""
    if card_key and card_key.split("|")[1] == "email":
        return card, card_key
    emails = [i for i in items if i.channel == "email" and i.language == "english"]
    same = [i for i in emails if i.relationship == relationship]
    base, scope = (same, relationship) if len(same) >= style.MIN_EXAMPLES else (emails, "*")
    if len(base) < style.MIN_EXAMPLES:
        return card, card_key
    habits = style.card(examples(base))
    merged = {**card, **{k: habits[k] for k in ("greetings", "sign_offs", "length")}}
    return merged, f"{card_key or '*|*|*|*'} + {scope}|email habits"


def _allowed(item: StoredItem, ex_engine: ExclusionEngine, row: Any) -> bool:
    people = [(p["p"], list(p["d"])) for p in row.people]
    decision = ex_engine.lineage(
        people,
        thread_hash=item.thread_hash if item.channel == "email" else None,
        chat_hash=item.thread_hash if item.channel == "chat" else None,
        meeting_hash=row.meeting_hash,
        series_hash=row.series_hash,
    )
    return not decision.excluded


async def load_pack(
    conn: AsyncConnection,
    vault: Vault,
    ref: UserRef,
    source_kind: str,
    ctx: LiveContext,
    ex_engine: ExclusionEngine,
    hasher: Hasher,
) -> PersonaPack:
    cards = await load_cards(conn, vault, ref, source_kind)
    settings = await load_settings(conn, vault, ref)
    found = style.lookup(cards, ctx.audience.relationship, "email", "english") if cards else None
    card_key, card = found if found else (None, DEFAULT_CARD)
    items = await load_items(conn, vault, ref, source_kind)
    lineage = {
        str(r.id): r
        for r in (
            await conn.execute(
                text("select id, people, meeting_hash, series_hash from vanimo.l1_items where source_kind = :k"),
                {"k": source_kind},
            )
        ).all()
    }
    allowed_items = [i for i in items if i.id in lineage and _allowed(i, ex_engine, lineage[i.id])]
    card, card_key = _email_habits(card, card_key, allowed_items, ctx.audience.relationship)
    thread_hash = hasher("thread", ctx.conversation_id) if ctx.conversation_id else None
    people = {hasher("person", r.address.email) for r in ctx.audience.to + ctx.audience.cc}
    query = embed(ctx.last_received or ctx.instruction or ctx.subject or "")
    scored: list[tuple[float, StoredItem, str]] = []
    excluded = len(items) - len(allowed_items)
    for item in allowed_items:
        row = lineage[item.id]
        same_thread = thread_hash is not None and item.thread_hash == thread_hash
        same_people = bool(people & {p["p"] for p in row.people})
        sim = cosine(query, item.vec) if item.vec else 0.0
        score = sim + (2.0 if same_thread else 0) + (1.0 if same_people else 0)
        score += (0.15 if item.relationship == ctx.audience.relationship else 0) + (
            0.1 if item.channel == "email" else 0
        )
        if not (same_thread or same_people) and sim < MIN_SIMILARITY:
            continue
        scored.append((score, item, "same_thread" if same_thread else "same_people" if same_people else "similar"))
    scored.sort(key=lambda s: -s[0])
    exemplars = [
        Exemplar(
            text=item.text if why != "similar" else skeleton(item),
            verbatim=why != "similar",
            relationship=item.relationship,
            why=why,
        )
        for _, item, why in scored[:MAX_EXEMPLARS]
    ]
    wanted = {t for ex in exemplars if ex.verbatim for t in TOKEN.findall(ex.text)}
    stored: dict[str, str] = {}
    if wanted:
        for r in (
            await conn.execute(
                text("select token, value_enc from vanimo.l1_tokens where token = any(:t)"), {"t": sorted(wanted)}
            )
        ).all():
            stored[r.token] = vault.decrypt_user(ref.tenant_id, ref.user_id, r.value_enc, "l1_token") or ""
    return PersonaPack(
        card_key=card_key,
        card=card,
        overall=cards.get(style.slice_key()),
        settings=settings,
        exemplars=exemplars,
        stored_tokens=stored,
        excluded_items=excluded,
    )
