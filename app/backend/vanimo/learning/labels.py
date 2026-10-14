"""Labels for each learned item (architecture §9.2): relationship, intent, channel and language.

Rules only — no model sees anything here. Relationship comes from the directory (manager,
direct reports) and domains (the organisation's own, consumer mail); intent from cue phrases;
language mode from script and a romanised-Hindi lexicon (Hinglish is a first-class style).
Labels run on L1 text, so tokens like ⟦PERSON_…⟧ never count as words.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Literal

from vanimo.sources.base import CONSUMER_DOMAINS, Address

Relationship = Literal["manager", "report", "peer", "external", "personal"]
Language = Literal["english", "hinglish", "hindi"]

_TOKENS = re.compile(r"⟦[^⟦⟧]{1,40}⟧|\[[A-Za-z ]{2,30}\]")
_WORD = re.compile(r"[A-Za-zऀ-ॿ']+")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")

# Common romanised Hindi function words and fillers. Kept to words that are rare in English.
HINGLISH = frozenset(
    """
    hai hain tha thi kya kyu kyun nahi nahin haan haa accha acha achha theek thik thk karo kar
    karna karenge karte karta kardo kardunga raha rahi rahe hoga hogi hona ho gaya gayi gaye kal aaj abhi
    bas yaar yar bhai bhaiya ji arre arey chalo chal matlab bilkul sahi zaroor jaldi thoda thodi bahut
    mein mujhe mera meri mere tum tumhe tera aap aapka aapki apna hum hamara humko unka unki
    wala wali wale kaise kaisa kuch koi sab sabko lekin aur bhi toh phir agar jab
    dekh dekho dekhte batao bata bolo bol samjha samajh pata lena dena dedo chahiye sakte sakta
    hua hui huye kab kahan yahan wahan iska uska isko usko unko kitna kitne zyada jyada
    """.split()
)

_INTENTS: list[tuple[str, re.Pattern[str]]] = [
    ("thanks", re.compile(r"^\W*(thanks|thank you|many thanks|thx|ty)\b[^?]{0,80}$", re.I | re.S)),
    ("apology", re.compile(r"\b(sorry|apologi[sz]e|apologies|my bad)\b", re.I)),
    (
        "scheduling",
        re.compile(
            r"\b(meeting|call|calendar|invite|slot|reschedul\w*|prepone|postpone|"
            r"available|availability|tomorrow at|cutover window|bridge)\b",
            re.I,
        ),
    ),
    (
        "request",
        re.compile(
            r"\b(please|pls|kindly|could you|can you|can we|would you|request|need you to|"
            r"share|send|review|confirm|karo|kardo|bhejo|batao)\b",
            re.I,
        ),
    ),
    (
        "update",
        re.compile(
            r"\b(update|status|fyi|pfa|attached|highlights|done|completed|deployed|"
            r"migrated|shared|on track|progress|ho gaya)\b",
            re.I,
        ),
    ),
    ("question", re.compile(r"\?")),
]
INTENTS = [name for name, _ in _INTENTS] + ["general"]


def words(l1: str) -> list[str]:
    return _WORD.findall(_TOKENS.sub(" ", l1))


def language(l1: str) -> Language:
    text = _TOKENS.sub(" ", l1)
    if len(_DEVANAGARI.findall(text)) >= 3:
        return "hindi"
    ws = [w.lower() for w in _WORD.findall(text)]
    if not ws:
        return "english"
    hits = sum(1 for w in ws if w in HINGLISH)
    return "hinglish" if hits >= 2 and hits / len(ws) >= 0.12 else "english"


def intent(l1: str) -> str:
    for name, pattern in _INTENTS:
        if pattern.search(_TOKENS.sub(" ", l1)):
            return name
    return "general"


def _in(domain: str, domains: Iterable[str]) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in domains)


def relationship(
    audience: Iterable[Address],
    *,
    manager: str | None,
    reports: frozenset[str],
    org_domains: frozenset[str],
) -> Relationship:
    """Who the user is writing to. Any external business participant makes it "external" (the
    most careful register); otherwise the manager, then reports, then peers."""
    people = [a for a in audience if a.email]
    if not people:
        return "peer"
    emails = {a.email.lower() for a in people}
    external = [a for a in people if not _in(a.domain, org_domains)]
    if any(not _in(a.domain, CONSUMER_DOMAINS) for a in external):
        return "external"
    if external:
        return "personal"
    if manager and manager.lower() in emails:
        return "manager"
    if emails <= reports:
        return "report"
    return "peer"
