"""Draft ↔ sent comparison (architecture §9.2 "edit-feedback loop", research R05 §2.3 and §7.7).

Both sides are L1 (the same tokens for the same people, the same never-send placeholders), so
names never count as edits. Rules only, no model:

  outcome     sent_as_is (≤ 5 % of characters changed) · light_edit (≤ 25 %) · heavy_edit ·
              rewritten (more than 25 % changed and little text in common)
  style edits greeting · sign-off · length (shorter / longer) · exclamation marks dropped ·
              a filler or politeness phrase deleted ("please do not hesitate") · one word swapped
              for another ("please" → "pls")
  content     anything touching numbers, dates, names, slots or longer passages: counted, never
              turned into a style rule (R05: content edits are not style)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Literal

from vanimo.controls.neversend import REMOVED
from vanimo.learning import style
from vanimo.redaction.marks import L1_MARKS, NEVER_SEND

SENT_AS_IS = 0.05
LIGHT_EDIT = 0.25
REWRITE_SIMILARITY = 0.3  # character 5-gram overlap below this: a different text, not an edit
MIN_WORDS_FOR_LENGTH = 8

Outcome = Literal["sent_as_is", "light_edit", "heavy_edit", "rewritten"]
EditKind = Literal["greeting", "sign_off", "length", "avoid", "prefer", "exclamations", "content"]

_TOKEN = re.compile(rf"{L1_MARKS.pattern}|\[[^\]\n]{{1,40}}\]|[\w']+|[^\w\s]")
_WORD = re.compile(r"[a-z][a-z']*")
# Words that make a deleted phrase a habit worth learning (fillers, politeness formulas).
FORMULA = frozenset(
    """please kindly hope hoping just hesitate feel free reach out let know happy glad apologies sorry
    thanks thank appreciate appreciated wanted would like certainly absolutely really truly sincerely
    note advise assure assured rest great wonderful touch base circle back quick""".split()
)


# Phrases that are filler wherever they appear ("please do not hesitate to reach out").
FILLER_PHRASES = (
    "do not hesitate", "don't hesitate", "feel free", "reach out", "touch base", "circle back", "hope you",
    "hope this", "let me know", "just wanted", "just checking", "kindly note", "please note", "i trust",
    "rest assured", "happy to help", "thanks in advance", "have a great", "have a good",
)  # fmt: skip


@dataclass(frozen=True)
class Edit:
    kind: EditKind
    value: str = ""  # L1 form or phrase for style edits; empty for content


@dataclass
class Comparison:
    outcome: Outcome
    edit_share: float  # share of characters changed, 0..1
    similarity: float
    draft_words: int
    sent_words: int
    edits: list[Edit] = field(default_factory=list)


def _clean(text: str) -> str:
    return "\n".join(" ".join(line.split()) for line in text.strip().splitlines() if line.strip())


def similarity(a: str, b: str, n: int = 5) -> float:
    """Character n-gram Jaccard overlap."""

    def grams(t: str) -> set[str]:
        t = " ".join(t.lower().split())
        return {t[i : i + n] for i in range(max(len(t) - n + 1, 1))}

    ga, gb = grams(a), grams(b)
    return len(ga & gb) / len(ga | gb) if ga | gb else 1.0


def edit_share(a: str, b: str) -> float:
    return round(1 - SequenceMatcher(None, _clean(a), _clean(b), autojunk=False).ratio(), 4)


def outcome_of(share: float, sim: float) -> Outcome:
    if share <= SENT_AS_IS:
        return "sent_as_is"
    if share <= LIGHT_EDIT:
        return "light_edit"
    return "heavy_edit" if sim >= REWRITE_SIMILARITY else "rewritten"


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text)


def _is_word(tok: str) -> bool:
    return bool(_WORD.fullmatch(tok.lower())) and not L1_MARKS.fullmatch(tok)


_TRAILING = frozenset("if to the a an and for of you me us on in with at".split())
# A swapped word that carries facts is a content edit, never a style preference.
_DATE_NAMES = frozenset(
    """monday tuesday wednesday thursday friday saturday sunday today tomorrow yesterday tonight january
    february march april may june july august september october november december jan feb mar apr jun jul aug
    sep sept oct nov dec eod eow""".split()
)
_FACT_WORDS = _DATE_NAMES | frozenset("week month year morning afternoon evening noon".split())


def _swappable(tok: str) -> bool:
    """A lower-case everyday word: not a name or product (capitalised mid-text), a date or a number."""
    return _is_word(tok) and tok == tok.lower() and tok.lower() not in _FACT_WORDS


def style_edits(draft: str, sent: str) -> list[Edit]:
    out: list[Edit] = []
    g_d, g_s = style.greeting_of(draft), style.greeting_of(sent)
    if g_d != g_s:
        out.append(Edit("greeting", g_s or "(none)"))
    s_d, s_s = style.sign_off_of(draft), style.sign_off_of(sent)
    if s_d != s_s:
        out.append(Edit("sign_off", s_s or "(none)"))
    body_d = style.body_lines(draft) or draft
    body_s = style.body_lines(sent) or sent
    w_d, w_s = len(style._words(body_d)), len(style._words(body_s))
    if w_d >= MIN_WORDS_FOR_LENGTH:
        if w_s / w_d < 0.75:
            out.append(Edit("length", "shorter"))
        elif w_s / w_d > 1.33:
            out.append(Edit("length", "longer"))
    if "!" in body_d and "!" not in body_s:
        out.append(Edit("exclamations", "none"))
    t_d, t_s = _tokens(body_d), _tokens(body_s)
    matcher = SequenceMatcher(None, [t.lower() for t in t_d], [t.lower() for t in t_s], autojunk=False)
    content = False
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        old, new = t_d[i1:i2], t_s[j1:j2]
        if tag == "replace" and len(old) == 1 and len(new) == 1 and _swappable(old[0]) and _swappable(new[0]):
            out.append(Edit("prefer", f"{old[0].lower()} -> {new[0].lower()}"))
        elif tag == "delete" and 2 <= len(old) <= 16 and all(_is_word(t) or re.fullmatch(r"[,.!?]", t) for t in old):
            words = [t.lower() for t in old if _is_word(t)]
            formulas = sum(w in FORMULA for w in words)
            # A short filler phrase, or a whole deleted sentence that is mostly filler.
            share = formulas / len(words) if words else 0
            joined = " ".join(words)
            filler = any(f in joined for f in FILLER_PHRASES) or (
                share >= 0.3 if len(words) <= 6 else (formulas >= 2 and share >= 0.25)
            )
            if len(words) >= 2 and filler and not _DATE_NAMES & set(words):
                phrase = words[:8]
                while len(phrase) > 2 and phrase[-1] in _TRAILING:
                    phrase.pop()
                out.append(Edit("avoid", " ".join(phrase)))
            else:
                content = True
        else:
            content = True
    if content:
        out.append(Edit("content"))
    # One of each value: the same swap twice in a message is one observation.
    return list(dict.fromkeys(out))


def compare(draft_l1: str, sent_l1: str) -> Comparison:
    # A never-send word shows as [removed] on screen; what the user sends back carries that text.
    draft_l1, sent_l1 = (NEVER_SEND.sub(REMOVED, t) for t in (draft_l1, sent_l1))
    share = edit_share(draft_l1, sent_l1)
    sim = similarity(draft_l1, sent_l1)
    result = outcome_of(share, sim)
    return Comparison(
        outcome=result,
        edit_share=share,
        similarity=round(sim, 4),
        draft_words=len(style._words(draft_l1)),
        sent_words=len(style._words(sent_l1)),
        # A rewrite is a different message: nothing in it says how the draft should have been styled.
        edits=[] if result in ("sent_as_is", "rewritten") else style_edits(draft_l1, sent_l1),
    )
