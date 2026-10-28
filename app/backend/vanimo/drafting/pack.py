"""The persona pack for one draft (architecture §9.2; F15 tone groups): how the user writes in this channel
and tone, how they greet this person, the tone's vocabulary for what this draft does, their studio
settings, the rules learned from their edits, and a few of their own past messages as examples.

Style (F15):
  * the channel card (greeting, sign-off, length) comes from this bucket only (email, a Teams 1:1 chat or a
    group): a chat never gets "Dear …, Best regards";
  * the voice card (register, phrases, vocabulary) is the tone's, shared by every channel of that tone;
  * the person card says how the user opens and closes messages to this person here ("Bhai", "Hi Rahul,").

Examples (exemplars), ranked by similarity to what is being answered, nothing else:
  * every stored item is re-checked against the live exclusion rules first (§6.5 X5): a rule added a
    moment ago wins even before the purge job has deleted the item;
  * first from this conversation — the same thread or chat, or a message everyone on this email already
    received — given verbatim (nothing in it is new to anyone here), skipping what the thread already shows;
  * then from other conversations of the same channel and tone, only as a structure skeleton (greeting
    form, length, kind of message), so facts from one audience never reach another (§10), and only above
    MIN_SIMILARITY: no example is better than an unrelated one (the tone and vocabulary carry the voice).
    This conversation's own messages need no minimum: they show how the user writes to these very people.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from vanimo.controls.engine import ExclusionEngine
from vanimo.controls.neversend import Matcher
from vanimo.db.session import UserRef
from vanimo.drafting.context import LiveContext
from vanimo.edits.rules import Rule, rules_for_draft
from vanimo.learning import style, vocab
from vanimo.learning.embed import cosine, embed
from vanimo.learning.persona import (
    PersonaSettings,
    StoredItem,
    load_cards,
    load_items,
    load_settings,
    mask_settings,
)
from vanimo.redaction.marks import L1_MARKS, TOKEN
from vanimo.redaction.pipeline import Hasher
from vanimo.vault import Vault

MAX_EXEMPLARS = 3
MIN_SIMILARITY = 0.12
VOCAB_PER_SITUATION = 5

# Before anything is learned for this channel: a neutral card, clearly reported to the user as such.
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
# A chat's neutral habits: no sign-off, short.
DEFAULT_CHAT_CARD: dict[str, Any] = DEFAULT_CARD | {
    "greetings": [["(none)", 1.0]],
    "sign_offs": [["(none)", 1.0]],
    "length": {"median": 18, "p25": 8, "p75": 30},
}


@dataclass(frozen=True)
class Exemplar:
    text: str  # L1: the message itself (verbatim) or its skeleton
    verbatim: bool
    tone: str
    bucket: str
    why: str  # content-free: conversation | similar


@dataclass
class PersonaPack:
    card_key: str | None  # the channel card's slice (None: the neutral default)
    card: dict[str, Any]  # greeting, sign-off and length habits, from this bucket
    overall: dict[str, Any] | None
    settings: PersonaSettings
    exemplars: list[Exemplar]
    stored_tokens: dict[str, str] = field(default_factory=dict)  # owner's values for tokens in exemplars
    rules: list[Rule] = field(default_factory=list)  # learned from edits (M4): active and confirmed
    excluded_items: int = 0  # items the live rules filtered out (logical exclusion before purge)
    voice_key: str | None = None
    voice: dict[str, Any] | None = None  # the tone's register, phrases and vocabulary (all channels)
    person: dict[str, Any] | None = None  # how the user greets this person in this channel
    vocabulary: dict[str, list[str]] = field(default_factory=dict)  # situation → the user's phrases
    spellings: list[dict[str, Any]] = field(default_factory=list)

    @property
    def learned(self) -> bool:
        return self.card.get("n", 0) > 0 or bool(self.voice and self.voice.get("n", 0) > 0)


def skeleton(item: StoredItem) -> str:
    """The shape of a message without its content."""
    greeting = style.greeting_of(item.text)
    sign_off = style.sign_off_of(item.text)
    words = len(style._words(style.body_lines(item.text) or item.text))
    parts = [greeting or "(no greeting)", f"[{words} words: {item.intent}]", sign_off or "(no sign-off)"]
    return "\n".join(parts)


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


def _mask_card(card: dict[str, Any], matcher: Matcher) -> dict[str, Any]:
    """A card's phrases, forms and vocabulary re-checked against the user's never-send words as they are
    now: a word added a moment ago never reaches the model, even before the scrub job has re-masked what's
    stored (§6.5 X5). A vocabulary phrase holding one is dropped (it would only be a placeholder)."""
    if not matcher:
        return card

    def m(value: str) -> str:
        return matcher.mask(value, opaque=L1_MARKS)[0] or ""

    out = dict(card)
    out["phrases"] = [m(x) for x in card.get("phrases", [])]
    for key in ("greetings", "sign_offs"):
        out[key] = [[m(str(form)), share] for form, share in card.get(key, [])]
    if "vocab" in card:
        out["vocab"] = {
            s: [p for p in phrases if not matcher.count(p["phrase"])] for s, phrases in card["vocab"].items()
        }
    return out


def _verbatim(item_people: set[str], audience: set[str]) -> bool:
    """A past message may be shown to the model word for word only if everyone this email goes to
    already received it: then nothing in it can reach someone who didn't see it."""
    return bool(audience) and audience <= item_people


async def load_pack(
    conn: AsyncConnection,
    vault: Vault,
    ref: UserRef,
    source_kind: str,
    ctx: LiveContext,
    ex_engine: ExclusionEngine,
    hasher: Hasher,
    matcher: Matcher,
) -> PersonaPack:
    a = ctx.audience
    cards = await load_cards(conn, vault, ref, source_kind)
    settings = mask_settings(await load_settings(conn, vault, ref), matcher)
    found = style.channel_card(cards, a.tone, a.bucket, "english")
    card_key, card = found if found else (None, DEFAULT_CHAT_CARD if ctx.channel == "chat" else DEFAULT_CARD)
    voice_found = style.voice_card(cards, a.tone)
    voice_key, voice = voice_found if voice_found else (None, None)
    person = cards.get(style.person_key(a.counterpart, a.bucket)) if a.counterpart else None
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
    kind = "chat" if ctx.channel == "chat" else "thread"
    thread_hash = hasher(kind, ctx.conversation_id) if ctx.conversation_id else None
    audience = {hasher("person", r.address.email) for r in a.to + a.cc}
    query = embed(ctx.last_received or ctx.instruction or ctx.subject or "")
    shown = {m.text.strip() for m in ctx.thread}
    here: list[tuple[float, StoredItem]] = []
    elsewhere: list[tuple[float, StoredItem]] = []
    for item in allowed_items:
        if item.text.strip() in shown:
            continue
        sim = cosine(query, item.vec) if item.vec else 0.0
        same_thread = thread_hash is not None and item.thread_hash == thread_hash and item.channel == ctx.channel
        if same_thread or _verbatim({p["p"] for p in lineage[item.id].people}, audience):
            here.append((sim, item))
        elif item.bucket == a.bucket and item.tone == a.tone and sim >= MIN_SIMILARITY:
            elsewhere.append((sim, item))
    here.sort(key=lambda s: -s[0])
    elsewhere.sort(key=lambda s: -s[0])
    chosen = [(i, "conversation") for _, i in here[:MAX_EXEMPLARS]]
    chosen += [(i, "similar") for _, i in elsewhere[: MAX_EXEMPLARS - len(chosen)]]
    exemplars = [
        Exemplar(
            text=(matcher.mask(item.text if why == "conversation" else skeleton(item), opaque=L1_MARKS)[0] or ""),
            verbatim=why == "conversation",
            tone=item.tone,
            bucket=item.bucket,
            why=why,
        )
        for item, why in chosen
    ]
    wanted = {t for ex in exemplars if ex.verbatim for t in TOKEN.findall(ex.text)}
    stored: dict[str, str] = {}
    if wanted:
        for r in (
            await conn.execute(
                text("select token, value_enc from vanimo.l1_tokens where token = any(:t)"), {"t": sorted(wanted)}
            )
        ).all():
            value = vault.decrypt_user(ref.tenant_id, ref.user_id, r.value_enc, "l1_token") or ""
            stored[r.token] = matcher.mask(value)[0] or ""
    overall = cards.get(style.slice_key())
    learned = await rules_for_draft(conn, vault, ref, source_kind, a.relationship, matcher)
    voice = _mask_card(voice, matcher) if voice else None
    bank = (voice or {}).get("vocab", {})
    vocabulary = {
        s: [p["phrase"] for p in bank[s][:VOCAB_PER_SITUATION]]
        for s in vocab.for_draft(ctx.instruction, ctx.last_received)
        if bank.get(s)
    }
    return PersonaPack(
        card_key=card_key,
        card=_mask_card(card, matcher),
        overall=_mask_card(overall, matcher) if overall else None,
        settings=settings,
        exemplars=exemplars,
        stored_tokens=stored,
        rules=learned,
        excluded_items=len(items) - len(allowed_items),
        voice_key=voice_key,
        voice=voice,
        person=_mask_card(person, matcher) if person and person.get("n", 0) >= style.MIN_PERSON else None,
        vocabulary=vocabulary,
        spellings=list((overall or {}).get("spellings", [])),
    )
