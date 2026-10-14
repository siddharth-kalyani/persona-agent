"""Style cards (architecture §9.2): how the user writes, per slice, computed from L1 only.

A slice is relationship | channel | language | intent, with "*" for "any". Cards exist at five
levels (all → relationship → +channel → +language → +intent); lookup backs off to the most
specific card with enough examples, so a sparse slice borrows from its parent.

Everything here is deterministic and model-free. Names never appear in a card: greetings and
sign-offs keep only the *form* ("Hi {first},", "Best regards,\\n{me_full}"), and phrases
containing a token, a masked slot or a never-send placeholder are discarded.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

MIN_EXAMPLES = 3
TOP_FORMS = 3
TOP_PHRASES = 8

_FORM_TOKENS = [
    (re.compile(r"⟦ME\.full⟧"), "{me_full}"),
    (re.compile(r"⟦ME(?:\.last)?⟧"), "{me}"),
    (re.compile(r"⟦PERSON_[0-9a-f]{8}\.full⟧"), "{full}"),
    (re.compile(r"⟦PERSON_[0-9a-f]{8}\.last⟧"), "{last}"),
    (re.compile(r"⟦PERSON_[0-9a-f]{8}⟧"), "{first}"),
]
_ANY_MARK = re.compile(r"⟦[^⟦⟧]{1,40}⟧|\[[A-Za-z ]{2,30}\]")
_GREETING = re.compile(
    r"^(hi|hii+|hello|hey|heya|dear|good (?:morning|afternoon|evening)|namaste|respected|greetings|"
    r"hi all|hello all|hi team|hello team|team|all)\b",
    re.I,
)
_CLOSING = re.compile(
    r"^(thanks|thank you|thanks again|many thanks|thx|ty|regards|best|best regards|kind regards|warm regards|"
    r"cheers|br|sincerely|take care|talk soon|see you|shukriya|dhanyavaad)\b",
    re.I,
)
_WORD = re.compile(r"[a-zऀ-ॿ']+")
_EMOJI = re.compile("[\U0001f300-\U0001faff☀-➿]")
FORMAL = frozenset("dear kindly regards sincerely please would request appreciate assistance confirm".split())
INFORMAL = frozenset("hey cheers yeah yep nope gonna wanna lol btw yaar bhai ok okay cool awesome thx".split())
# Indian-English usages kept as the user's own voice, never "corrected" (architecture §9.2).
KEEP_LIST = (
    "pfa",
    "revert",
    "prepone",
    "kindly",
    "do the needful",
    "ji",
    "lakh",
    "crore",
    "at the earliest",
    "updated",
    "same",
    "itself",
    "only",
    "out of station",
)
_STOP = frozenset(
    "the a an to of and or in on for is it this that we i you be with at as are was by our your my me "
    "will can so if from have has had not do does but".split()
)


@dataclass(frozen=True)
class Example:
    text: str  # L1
    relationship: str
    channel: str
    language: str
    intent: str
    thread: str


# Words a greeting or sign-off may keep; any other capitalised word there is taken to be a name
# the gazetteer didn't know ("Hi Rao,", "Cheers, Sid") and becomes {name}.
_FORM_WORDS = frozenset(
    "hi hii hiii hello hey heya dear good morning afternoon evening namaste respected greetings all team "
    "everyone folks guys sir madam maam ma'am mr mrs ms dr prof shri smt ji thanks thank you again many thx ty "
    "regards best kind warm warmest cheers br sincerely take care talk soon see shukriya dhanyavaad and the "
    "with love yours truly faithfully".split()
)


def form(line: str) -> str:
    for pattern, repl in _FORM_TOKENS:
        line = pattern.sub(repl, line)
    line = re.sub(
        r"(?<![{\w])[A-Z\u00c0-\u024f][\w'\u2019.-]*",
        lambda m: m.group() if m.group().lower().strip(".") in _FORM_WORDS else "{name}",
        line,
    )
    return " ".join(line.split())


def greeting_of(l1: str) -> str | None:
    lines = [ln.strip() for ln in l1.strip().splitlines() if ln.strip()]
    if not lines:
        return None
    first = lines[0]
    # "Hi ⟦PERSON_…⟧, can you…" (chat) → the greeting is the part before the first comma.
    head = re.split(r"(?<=[,!])\s", first, maxsplit=1)[0]
    if _GREETING.match(head) and len(head.split()) <= 6:
        return form(head)
    return None


def sign_off_of(l1: str) -> str | None:
    lines = [ln.strip() for ln in l1.strip().splitlines() if ln.strip()]
    if len(lines) < 2 and not (lines and re.search(r"⟦ME", lines[-1])):
        return None
    last = lines[-1]
    if re.fullmatch(r"⟦ME(?:\.full)?⟧\.?", last) and len(lines) >= 2 and len(lines[-2].split()) <= 4:
        return form(f"{lines[-2]}\n{last}")
    if _CLOSING.match(last) and len(last.split()) <= 5:
        return form(last)
    return None


def body_lines(l1: str) -> str:
    """The text without its greeting and sign-off lines."""
    lines = [ln for ln in l1.strip().splitlines()]
    if lines and greeting_of(lines[0]) and len(lines[0].split()) <= 6:
        lines = lines[1:]
    tail = "\n".join(lines[-2:])
    if lines and sign_off_of(tail):
        lines = lines[:-2] if re.fullmatch(r"\s*⟦ME(?:\.full)?⟧\.?\s*", lines[-1]) else lines[:-1]
    return "\n".join(lines).strip()


def _words(l1: str) -> list[str]:
    return _WORD.findall(_ANY_MARK.sub(" | ", l1.lower()))


def formality(texts: Sequence[str]) -> float:
    """0 = very casual, 1 = very formal: share of formal vs informal cue words."""
    f = i = 0
    for t in texts:
        ws = _words(t)
        f += sum(1 for w in ws if w in FORMAL)
        i += sum(1 for w in ws if w in INFORMAL)
        i += t.count("!") // 2 + len(_EMOJI.findall(t))
    return round((f + 1) / (f + i + 2), 2)


def _ngrams(l1: str) -> set[str]:
    out: set[str] = set()
    for segment in _ANY_MARK.split(l1.lower()):  # never across a token or slot
        ws = _WORD.findall(segment)
        for n in (2, 3, 4):
            for k in range(len(ws) - n + 1):
                gram = ws[k : k + n]
                if all(w in _STOP for w in gram) or (gram[0] in _STOP and gram[-1] in _STOP):
                    continue
                out.add(" ".join(gram))
    return out


def proper_nouns(texts: Iterable[str]) -> set[str]:
    """Words only ever written capitalised mid-sentence: likely names the gazetteer didn't know
    (and client or product names). Phrases containing them are not kept in a card."""
    capital: set[str] = set()
    lower: set[str] = set()
    for t in texts:
        for m in re.finditer(r"(?<=[^.!?\n\s])\s+([A-Za-z][A-Za-z']+)", _ANY_MARK.sub(" | ", t)):
            w = m.group(1)
            (capital if w[0].isupper() else lower).add(w.lower())
    return capital - lower


def phrases(examples: Iterable[Example]) -> list[str]:
    """Recurring phrases: used in at least 2 messages across at least 2 threads, with no likely
    proper noun in them."""
    examples = list(examples)
    names = proper_nouns(ex.text for ex in examples)
    count: Counter[str] = Counter()
    threads: dict[str, set[str]] = {}
    for ex in examples:
        for g in _ngrams(body_lines(ex.text) or ex.text):
            count[g] += 1
            threads.setdefault(g, set()).add(ex.thread)
    ranked = sorted(
        (g for g, c in count.items() if c >= 2 and len(threads[g]) >= 2 and not names & set(g.split())),
        key=lambda g: (-count[g] * len(g.split()), g),
    )
    chosen: list[str] = []
    for g in ranked:
        if any(g in c for c in chosen):
            continue
        chosen = [c for c in chosen if c not in g] + [g]
        if len(chosen) >= TOP_PHRASES:
            break
    return chosen


def _dist(values: Iterable[str | None], top: int = TOP_FORMS) -> list[list[Any]]:
    vals = [v if v is not None else "(none)" for v in values]
    c = Counter(vals)
    return [[k, round(n / len(vals), 2)] for k, n in c.most_common(top)] if vals else []


def card(examples: Sequence[Example]) -> dict[str, Any]:
    texts = [e.text for e in examples]
    lengths = sorted(len(_words(body_lines(t) or t)) for t in texts)
    q = statistics.quantiles(lengths, n=4) if len(lengths) >= 2 else [lengths[0]] * 3
    joined = " ".join(t.lower() for t in texts)
    return {
        "n": len(examples),
        "greetings": _dist(greeting_of(t) for t in texts),
        "sign_offs": _dist(sign_off_of(t) for t in texts),
        "length": {"median": int(statistics.median(lengths)), "p25": int(q[0]), "p75": int(q[2])},
        "formality": formality(texts),
        "exclamation_rate": round(sum("!" in t for t in texts) / len(texts), 2),
        "question_rate": round(sum("?" in t for t in texts) / len(texts), 2),
        "emoji_rate": round(sum(bool(_EMOJI.search(t)) for t in texts) / len(texts), 2),
        "phrases": phrases(examples),
        "keep_list": [k for k in KEEP_LIST if re.search(rf"\b{re.escape(k)}\b", joined)],
        "languages": dict(_dist((e.language for e in examples), top=3)),
        "intents": dict(_dist((e.intent for e in examples), top=6)),
    }


def slice_key(rel: str = "*", channel: str = "*", language: str = "*", intent: str = "*") -> str:
    return f"{rel}|{channel}|{language}|{intent}"


def slices(ex: Example) -> list[tuple[int, str]]:
    return [
        (0, slice_key()),
        (1, slice_key(ex.relationship)),
        (2, slice_key(ex.relationship, ex.channel)),
        (3, slice_key(ex.relationship, ex.channel, ex.language)),
        (4, slice_key(ex.relationship, ex.channel, ex.language, ex.intent)),
    ]


def build_cards(examples: Sequence[Example]) -> dict[str, tuple[int, dict[str, Any]]]:
    """slice key → (level, card). Level 0 always exists; others need MIN_EXAMPLES."""
    groups: dict[str, tuple[int, list[Example]]] = {}
    for ex in examples:
        for level, key in slices(ex):
            groups.setdefault(key, (level, []))[1].append(ex)
    return {
        key: (level, card(group))
        for key, (level, group) in groups.items()
        if group and (level == 0 or len(group) >= MIN_EXAMPLES)
    }


def lookup(
    cards: dict[str, dict[str, Any]], rel: str, channel: str, language: str = "*", intent: str = "*"
) -> tuple[str, dict[str, Any]] | None:
    """Most specific card with enough examples (back-off)."""
    for key in (
        slice_key(rel, channel, language, intent),
        slice_key(rel, channel, language),
        slice_key(rel, channel),
        slice_key(rel),
        slice_key(),
    ):
        if key in cards and (cards[key]["n"] >= MIN_EXAMPLES or key == slice_key()):
            return key, cards[key]
    return None
