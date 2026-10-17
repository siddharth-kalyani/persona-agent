"""Memory atoms from a meeting's L1 turns (MVP plan M6, research R05 §5.3).

L1 in, L1 out: turns are already redacted (names are person tokens, IDs are slots, never-send
words are placeholders), and every atom quotes a sentence of one turn, so a citation always points
at what was said. Types: decision, action item, commitment (a promise by the speaker), requirement,
open question, risk, idea. Two extractors behind one interface:

  * `OfflineAtomExtractor` — the clearly labelled stand-in until the AWS account exists (founder,
    2026-10-13): one atom per sentence at most, by cue phrases, precision first;
  * `BedrockAtomExtractor` (`vanimo/memory/model.py`) — Claude Haiku on windows of turns, every
    quote checked against the turn in code.

Who said it comes from the transcript (Teams' speaker attribution), never from a model. Due dates are
resolved in code from the sentence, in the cell's time zone (as for the commitments ledger).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

from vanimo.commitments.extract import _NEGATION, _VERBS, find_due, promises
from vanimo.redaction.marks import L1_MARKS

OFFLINE_LABEL = "Offline stand-in, no AI model: rule-based meeting notes"
Kind = Literal["decision", "action_item", "commitment", "requirement", "open_question", "risk", "idea"]
KINDS: tuple[Kind, ...] = ("decision", "action_item", "commitment", "requirement", "open_question", "risk", "idea")
Side = Literal["me", "internal", "external", "unknown"]
MAX_TEXT = 240
CONFIDENCE: dict[Kind, float] = {
    "decision": 0.75,
    "commitment": 0.7,
    "action_item": 0.7,
    "requirement": 0.65,
    "open_question": 0.6,
    "risk": 0.6,
    "idea": 0.55,
}


@dataclass(frozen=True)
class Turn:
    """One speaker turn, L1. `speaker` is a person token ("⟦PERSON_1a2b3c4d.full⟧", "⟦ME.full⟧") or
    None when the transcript is unattributed."""

    ordinal: int
    start_ms: int  # from the start of the episode's first transcript
    end_ms: int
    speaker: str | None
    side: Side
    text: str


@dataclass(frozen=True)
class Atom:
    kind: Kind
    turn: int  # the turn's ordinal (the evidence span is that turn)
    quote: str  # L1: the sentence as said (a span of the turn)
    text: str  # L1: short form
    owner: str | None  # person token: who should act (action item) or who promised (commitment)
    due_phrase: str | None
    due_at: datetime | None
    confidence: float


class AtomExtractor(Protocol):
    kind: Literal["offline", "bedrock"]

    async def find(self, turns: list[Turn], *, started_at: datetime, tz: ZoneInfo) -> list[Atom]: ...


# --- sentences ---------------------------------------------------------------------------------
_SPLIT = re.compile(r"(?<=[.!?])\s+")
_LEAD_IN = re.compile(r"^(?:(?:also|and|so|ok|okay|right|good|great|agreed|yes|sure|then|now)\b[,.!:]?\s+)+", re.I)
_PERSON = r"⟦(?:PERSON_[0-9a-f]{8}|ME)(?:\.full|\.last)?⟧"


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SPLIT.split(text) if len(s.strip().split()) >= 3]


def full_token(token: str) -> str:
    """A person token in its full-name form (the speaker and owner form): ⟦PERSON_x⟧ → ⟦PERSON_x.full⟧."""
    stem = token.removesuffix("⟧").removesuffix(".full").removesuffix(".last")
    return stem + ".full⟧"


def _short(sentence: str) -> str:
    s = _LEAD_IN.sub("", sentence).strip()
    s = s[:1].upper() + s[1:] if s else s
    return s[:MAX_TEXT].rstrip()


# --- rules -------------------------------------------------------------------------------------
_DECISION = re.compile(
    r"\b(?:we(?:['’]ve|\s+have)?\s+(?:all\s+)?(?:decided|agreed)"  # noqa: RUF001 - both apostrophes
    r"|(?:it['’]s|that['’]s|it\s+is)\s+(?:decided|agreed|settled)"  # noqa: RUF001
    r"|let['’]?s\s+go\s+(?:with|ahead)"  # noqa: RUF001
    r"|we(?:['’]ll|\s+will)\s+go\s+(?:ahead\s+)?with"  # noqa: RUF001
    r"|(?:final\s+)?decision(?:\s+is|\s+then)?\s*[:,\-–]"  # noqa: RUF001 - en dash
    r"|^agreed\b[,.!]\s*\S)",
    re.I,
)
_NOT_DECIDED = re.compile(r"\b(?:not\s+yet|haven['’]t|hasn['’]t|yet\s+to|undecided|if\s+we)\b", re.I)  # noqa: RUF001
_REQUEST = re.compile(
    rf"^(?:(?P<who>{_PERSON})\s*,\s*)?(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?|please\s+|kindly\s+)"
    rf"(?P<what>(?:{_VERBS})\b.*?)[.?!]?$",
    re.I,
)
_THIRD_PERSON = re.compile(rf"^(?P<who>{_PERSON})\s+(?:will|is\s+going\s+to|to)\s+(?P<what>(?:{_VERBS})\b.*?)[.!]?$")
_ACTION_LABEL = re.compile(r"^(?:action(?:\s+item)?|ai|to-?do)\s*[:\-–]\s*(?P<what>.+?)[.!]?$", re.I)  # noqa: RUF001
_IDEA = re.compile(
    r"\b(?:what\s+if|how\s+about|one\s+idea|an\s+idea|(?:an|one)\s+option\s+(?:is|would\s+be)|we\s+could"
    r"|maybe\s+we\s+(?:can|could|should)|why\s+don['’]t\s+we|i\s+suggest|my\s+suggestion)\b",  # noqa: RUF001
    re.I,
)
_REQUIREMENT = re.compile(
    r"\b(?:must|has\s+to|have\s+to|needs?\s+to|needs\b|need\b|requires?|required|requirement|mandatory"
    r"|non-negotiable|should\s+(?:be|support|have|load|stay|work))\b",
    re.I,
)
_NOT_REQUIREMENT = re.compile(
    r"^(?:i|i['’]m|i\s+am)\b|\b(?:don['’]t|doesn['’]t|no)\s+need\b|\bneed\s+(?:a\s+)?(?:break|minute|sec)",  # noqa: RUF001
    re.I,
)
_QUESTION = re.compile(
    r"\b(?:plan|option|decide|should\s+we|do\s+we|can\s+we|could\s+we|is\s+there|are\s+there|who\s+(?:will|owns|is)"
    r"|when\s+(?:will|do|can|should|are)|what\s+(?:about|happens))\b",
    re.I,
)
_OPEN = re.compile(
    r"\b(?:open\s+question|tbd|to\s+be\s+decided|still\s+need\s+to\s+(?:figure|decide|work)\s+out)\b", re.I
)
_RISK = re.compile(
    r"\b(?:risks?|blockers?|blocked|concerns?|concerned|worr(?:y|ied)|delay(?:ed|s)?|slips?|slipping|at\s+risk"
    r"|tight|bottleneck)\b",
    re.I,
)


def _other(turn: Turn, turns_by_speaker: set[str]) -> str | None:
    """In a two-person meeting, "please send…" is addressed to the other one."""
    others = [s for s in turns_by_speaker if s != turn.speaker]
    return others[0] if turn.speaker and len(others) == 1 else None


def classify(sentence: str, turn: Turn, speakers: set[str], *, said_at: datetime, tz: ZoneInfo) -> Atom | None:
    s = sentence.strip()
    body = _LEAD_IN.sub("", s)

    def atom(kind: Kind, text: str, owner: str | None = None) -> Atom:
        phrase, due = find_due(s, said_at, tz) if kind in ("action_item", "commitment") else (None, None)
        return Atom(kind, turn.ordinal, s, _short(text), owner, phrase, due, CONFIDENCE[kind])

    if _DECISION.search(s) and not _NOT_DECIDED.search(s):
        return atom("decision", s)
    found = promises(s, made_at=said_at, tz=tz)
    if found:
        return Atom(
            "commitment", turn.ordinal, s, _short(found[0].what), turn.speaker, found[0].due_phrase,
            found[0].due_at, CONFIDENCE["commitment"],
        )  # fmt: skip
    if (m := _REQUEST.match(body)) and not _NEGATION.search(body):
        who = m.group("who")
        owner = full_token(who) if who else _other(turn, speakers)
        return atom("action_item", m.group("what"), owner)
    if (m := _THIRD_PERSON.match(body)) or (m := _ACTION_LABEL.match(body)):
        who = m.groupdict().get("who")
        return atom("action_item", m.group("what"), full_token(who) if who else None)
    if _IDEA.search(s):
        return atom("idea", s)
    if not s.endswith("?") and _REQUIREMENT.search(s) and not _NOT_REQUIREMENT.search(body):
        return atom("requirement", s)
    if (s.endswith("?") and _QUESTION.search(s)) or _OPEN.search(s):
        return atom("open_question", s)
    if _RISK.search(s):
        return atom("risk", s)
    return None


def offline_atoms(turns: list[Turn], *, started_at: datetime, tz: ZoneInfo) -> list[Atom]:
    speakers = {t.speaker for t in turns if t.speaker}
    out: list[Atom] = []
    for t in turns:
        said_at = started_at + timedelta(milliseconds=max(t.start_ms, 0))
        for s in sentences(t.text):
            if "⟦" in L1_MARKS.sub("", s):
                continue  # a broken mark: never quote it
            a = classify(s, t, speakers, said_at=said_at, tz=tz)
            if a is not None:
                out.append(a)
    return out


class OfflineAtomExtractor:
    kind: Literal["offline", "bedrock"] = "offline"

    async def find(self, turns: list[Turn], *, started_at: datetime, tz: ZoneInfo) -> list[Atom]:
        return offline_atoms(turns, started_at=started_at, tz=tz)
