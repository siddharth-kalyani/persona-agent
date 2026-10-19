"""Never-send words: a deterministic matcher (no AI model ever sees the terms).

Design from docs/research/12 §6 and §9.6, rules-only variants (D5):
  1. Normalise text and terms identically on a *shadow copy* with an offset map back to the
     original: strip invisible/bidi characters, NFKC, case-fold, Devanagari digits → ASCII,
     common Cyrillic/Greek look-alikes → Latin, whitespace collapsed.
  2. Match every variant of every term. Word boundaries treat letters, combining marks and
     digits as word characters (so Devanagari matras stay attached — Python's `\\b` splits them).
  3. Replace each hit in the *original* text with the term's placeholder ⟦NS_xxxxxxxx⟧.

Term kinds:
  word      exact phrase + separator forms + plural/possessive, on word boundaries
  name      as word, plus glued honorifics/possessives (Sharma-ji, Sharmaji, Sharma's)
  codename  substring match, also on a "squashed" copy (project-falcon = projectfalcon)
Hinglish folding (aa→a, ee→i, oo→u, w→v, ph→f, doubled letters collapsed) is opt-in per word
(`Term.folds`) and its effect is shown to the user before saving: it catches "Sharmaa" for
"Sharma" but would also make "week" catch "Vik". Codenames shorter than 4 characters match as
whole words only. Text that is already masked (⟦NS_…⟧ placeholders) is never matched again.

The matcher never logs or returns term text; callers get counts and placeholders only.
"""

from __future__ import annotations

import re
import secrets
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

TermKind = Literal["word", "name", "codename"]

_INVISIBLE = frozenset(
    [0x00AD, 0x034F, 0x061C, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x180E, 0x200B, 0x200C, 0x200D, 0x200E, 0x200F]
    + list(range(0x202A, 0x202F))
    + list(range(0x2060, 0x2070))
    + [0x3164, 0xFEFF, 0xFFA0]
    + list(range(0xFE00, 0xFE10))
    + list(range(0xE0000, 0xE0080))
)
_DEVANAGARI_DIGITS = {0x0966 + i: str(i) for i in range(10)}
# A pragmatic subset of UTS #39 confusables: lookalikes used to dodge filters.
_CONFUSABLES = {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j", "ѕ": "s",
    "ԁ": "d", "ӏ": "l", "к": "k", "м": "m", "т": "t", "в": "b", "н": "h",
    "ɑ": "a", "ɡ": "g", "ı": "i", "ո": "n", "ս": "u", "օ": "o", "հ": "h", "ց": "g",
    "α": "a", "ο": "o", "ρ": "p", "ε": "e", "ι": "i", "κ": "k", "ν": "v", "τ": "t", "υ": "u", "χ": "x",
}  # fmt: skip
_NAME_SUFFIXES = ("ji", "jee", "sahab", "saheb", "bhai", "'s", "’s", "s", "जी", "भाई", "साहब")
_SEPARATORS = re.compile(r"[\s\-_./‐‑‒–—―−]+")
_PLACEHOLDER = re.compile(r"⟦NS_[0-9a-f]{8}⟧")


def _is_word_char(ch: str) -> bool:
    return unicodedata.category(ch)[0] in "LMN"


# For every shadow character: (index of the first, index of the last) source character it came from.
Span = tuple[int, int]


def _clusters(text: str) -> list[tuple[int, int, str]]:
    """(first index, last index, characters) per base character plus its combining marks, with
    invisible characters dropped — so "e" + U+0301 normalises like "é", and matras stay attached."""
    out: list[tuple[int, int, str]] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ord(ch) in _INVISIBLE or unicodedata.category(ch) == "Cf":
            i += 1
            continue
        j = i + 1
        chars = [ch]
        while j < len(text):
            nxt = text[j]
            if ord(nxt) in _INVISIBLE or unicodedata.category(nxt) == "Cf":
                j += 1
                continue
            if unicodedata.category(nxt)[0] != "M":
                break
            chars.append(nxt)
            j += 1
        out.append((i, j - 1, "".join(chars)))
        i = j
    return out


def normalise(text: str) -> tuple[str, list[Span]]:
    """Shadow copy of `text` plus, for every shadow character, the source characters it came from."""
    out: list[str] = []
    origin: list[Span] = []
    for first, last, cluster in _clusters(text):
        piece = unicodedata.normalize("NFKC", cluster).casefold()
        for c in piece:
            c = _DEVANAGARI_DIGITS.get(ord(c), c)
            c = _CONFUSABLES.get(c, c)
            if c.isspace():
                if out and out[-1] == " ":
                    continue
                c = " "
            out.append(c)
            origin.append((first, last))
    return "".join(out), origin


def _fold(shadow: str, origin: list[Span]) -> tuple[str, list[Span]]:
    """Hinglish folds on an already-normalised shadow copy, keeping the offset map."""
    rules = (("aa", "a"), ("ee", "i"), ("ii", "i"), ("oo", "u"), ("uu", "u"), ("ph", "f"))
    out: list[str] = []
    org: list[Span] = []
    i = 0
    while i < len(shadow):
        for src, dst in rules:
            if shadow.startswith(src, i):
                out.append(dst)
                org.append((origin[i][0], origin[i + len(src) - 1][1]))
                i += len(src)
                break
        else:
            c = "v" if shadow[i] == "w" else shadow[i]
            if out and out[-1] == c and c.isalpha() and c.isascii():
                org[-1] = (org[-1][0], origin[i][1])  # doubled letter folds into the previous one
            else:
                out.append(c)
                org.append(origin[i])
            i += 1
    return "".join(out), org


def _strip_marks(shadow: str, origin: list[Span]) -> tuple[str, list[Span]]:
    """Latin letters with their accents removed (UTS #39-style skeleton step), so a mark glued on
    to dodge the filter ("falcońs") doesn't hide the word. Non-Latin text is left as is."""
    out: list[str] = []
    org: list[Span] = []
    for c, o in zip(shadow, origin, strict=True):
        if unicodedata.category(c) in ("Mn", "Me") and out and out[-1].isascii() and out[-1].isalpha():
            # A mark NFKC couldn't merge (strikethrough U+0336, underline U+0332, ogonek on f):
            # it belongs to the Latin letter before it, so it goes and the letter keeps its span.
            org[-1] = (org[-1][0], o[1])
            continue
        d = unicodedata.normalize("NFD", c)
        if d[0].isascii():
            d = "".join(ch for ch in d if unicodedata.category(ch) not in ("Mn", "Me"))
        for ch in d:
            out.append(ch)
            org.append(o)
    return "".join(out), org


def _squash(shadow: str, origin: list[Span]) -> tuple[str, list[Span]]:
    keep = [(c, o) for c, o in zip(shadow, origin, strict=True) if not _SEPARATORS.fullmatch(c)]
    return "".join(c for c, _ in keep), [o for _, o in keep]


def _ascii_latin(s: str) -> bool:
    return all(c.isascii() for c in s)


@dataclass(frozen=True)
class Term:
    id: str
    text: str = field(repr=False)
    kind: TermKind = "word"
    extra_variants: tuple[str, ...] = field(default=(), repr=False)  # spellings the user typed or confirmed
    folds: bool = False  # Hinglish-folded matching, opted into by the user

    @property
    def placeholder(self) -> str:
        return f"⟦NS_{self.id}⟧"


def new_term_id() -> str:
    return secrets.token_hex(4)


MIN_SUBSTRING_CODENAME = 4


def folded_form(text: str) -> str | None:
    """What Hinglish folding reduces this word to (shown to the user before they opt in)."""
    base, _ = normalise(text.strip())
    base = base.strip()
    if not _ascii_latin(base) or len(base) < 4:
        return None
    folded, _ = _fold(base, [(k, k) for k in range(len(base))])
    return folded


def variants(text: str, kind: TermKind) -> list[str]:
    """Rule-based variants shown to the user for confirmation (normalised form)."""
    base, _ = normalise(text.strip())
    base = base.strip()
    if not base:
        return []
    tokens = [t for t in _SEPARATORS.split(base) if t]
    out = [base]
    if len(tokens) > 1:
        out += [" ".join(tokens), "-".join(tokens), "_".join(tokens), ".".join(tokens), "".join(tokens)]
    if kind in ("word", "codename") and _ascii_latin(base) and base[-1].isalpha():
        out += [base + "s", base + "es", base + "'s", base + "’s"]
    seen: set[str] = set()
    return [v for v in out if not (v in seen or seen.add(v))]


@dataclass
class _Pattern:
    term: Term
    needle: str
    space: Literal["plain", "stripped", "folded", "squashed"]
    boundary: bool


class Matcher:
    """Compiled from a user's terms; hold in memory only, never log."""

    def __init__(self, terms: list[Term]) -> None:
        self.terms = terms
        self._patterns: list[_Pattern] = []
        for term in terms:
            forms = variants(term.text, term.kind)
            for extra in term.extra_variants:
                norm, _ = normalise(extra.strip())
                if norm.strip():
                    forms.append(norm.strip())
            substring = term.kind == "codename" and len(normalise(term.text)[0].strip()) >= MIN_SUBSTRING_CODENAME
            for form in dict.fromkeys(forms):
                boundary = not substring
                self._patterns.append(_Pattern(term, form, "plain", boundary))
                stripped, _ = _strip_marks(form, [(k, k) for k in range(len(form))])
                if _ascii_latin(stripped):
                    self._patterns.append(_Pattern(term, stripped, "stripped", boundary))
                if term.folds and _ascii_latin(form) and len(form) >= 4:
                    # Matched against the folded copy of the text even when folding leaves the
                    # term unchanged: the *text* may fold ("Sharmaa" → "sharma").
                    folded, _ = _fold(form, [(k, k) for k in range(len(form))])
                    self._patterns.append(_Pattern(term, folded, "folded", boundary))
                if substring:
                    squashed, _ = _squash(form, [(k, k) for k in range(len(form))])
                    if len(squashed) >= 3:
                        self._patterns.append(_Pattern(term, squashed, "squashed", False))
        # Longest needles first, so "project falcon" wins over "falcon".
        self._patterns.sort(key=lambda p: len(p.needle), reverse=True)

    def __bool__(self) -> bool:
        return bool(self._patterns)

    def _spans(self, text: str) -> list[tuple[int, int, Term]]:
        plain, plain_map = normalise(text)
        spaces = {"plain": (plain, plain_map), "stripped": _strip_marks(plain, plain_map)}
        spaces["folded"] = _fold(plain, plain_map)
        spaces["squashed"] = _squash(plain, plain_map)
        hits: list[tuple[int, int, Term]] = []
        for p in self._patterns:
            shadow, origin = spaces[p.space]
            start = shadow.find(p.needle)
            while start != -1:
                end = start + len(p.needle)
                if p.boundary:
                    end = self._accept(shadow, start, end, p.term.kind)
                next_from = start + 1
                if end is not None:
                    s, e = origin[start][0], origin[end - 1][1] + 1
                    if not p.boundary:
                        # Substring hits mask the whole word they sit in ("Falconry" → [removed]);
                        # the rest of that word is covered, so the search resumes after it.
                        while s > 0 and _is_word_char(text[s - 1]):
                            s -= 1
                        while e < len(text) and _is_word_char(text[e]):
                            e += 1
                        next_from = end
                        while next_from < len(shadow) and _is_word_char(shadow[next_from]):
                            next_from += 1
                    hits.append((s, e, p.term))
                start = shadow.find(p.needle, next_from)
        return hits

    @staticmethod
    def _accept(shadow: str, start: int, end: int, kind: TermKind) -> int | None:
        if start > 0 and _is_word_char(shadow[start - 1]):
            return None
        if end == len(shadow) or not _is_word_char(shadow[end]):
            return end
        digits_end = end
        while digits_end < len(shadow) and shadow[digits_end].isdigit():
            digits_end += 1
        if digits_end > end and (digits_end == len(shadow) or not _is_word_char(shadow[digits_end])):
            return digits_end  # a version or number glued on: "Falcon2", "falcon2026"
        if kind == "name":  # glued honorific or possessive: Sharmaji, Sharma-ji is separator anyway
            for suffix in _NAME_SUFFIXES:
                if shadow.startswith(suffix, end):
                    after = end + len(suffix)
                    if after == len(shadow) or not _is_word_char(shadow[after]):
                        return after
        return None

    def mask(self, text: str | None, *, opaque: re.Pattern[str] | None = None) -> tuple[str | None, int]:
        """Replace every hit with its term's placeholder. Returns (masked text, number of hits).
        `opaque`: marks never matched inside or across (default: never-send placeholders; L1
        callers pass `vanimo.redaction.marks.L1_MARKS`, so tokens and [slots] stay intact)."""
        if not text or not self._patterns:
            return text, 0
        masked_spans = [(m.start(), m.end()) for m in (opaque or _PLACEHOLDER).finditer(text)]
        hits = sorted(
            (h for h in self._spans(text) if not any(h[0] < me and ms < h[1] for ms, me in masked_spans)),
            key=lambda h: (h[0], -(h[1] - h[0])),
        )
        merged: list[tuple[int, int, Term]] = []
        for s, e, t in hits:
            if merged and s < merged[-1][1]:
                ps, pe, pt = merged[-1]
                merged[-1] = (ps, max(pe, e), pt)
            else:
                merged.append((s, e, t))
        if not merged:
            return text, 0
        out: list[str] = []
        pos = 0
        for s, e, t in merged:
            out.append(text[pos:s])
            out.append(t.placeholder)
            pos = e
        out.append(text[pos:])
        return "".join(out), len(merged)

    def count(self, text: str | None, *, opaque: re.Pattern[str] | None = None) -> int:
        return self.mask(text, opaque=opaque)[1]


REMOVED = "[removed]"


def render_removed(text: str | None) -> str | None:
    """How masked text is shown: every never-send placeholder becomes [removed]."""
    return _PLACEHOLDER.sub(REMOVED, text) if text else text
