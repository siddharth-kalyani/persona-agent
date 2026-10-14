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
_NEGATIONS = frozenset("not no never cannot can't won't don't didn't isn't aren't wasn't shouldn't n't".split())


# A word swap is style only between forms that mean the same thing: everything else (accept →
# decline, last → next, office → warehouse, a → the) is a content edit and never becomes a rule.
SWAP_GROUPS = (
    frozenset({"please", "pls", "plz", "kindly"}),
    frozenset({"thanks", "thx", "thank", "ty", "tq", "thnx"}),
    frozenset({"ok", "okay", "alright", "fine", "sure"}),
    frozenset({"yes", "yeah", "yep", "yup"}),
    frozenset({"hi", "hello", "hey", "hii"}),
    frozenset({"revert", "reply", "respond"}),
    frozenset({"team", "all", "everyone", "folks", "guys"}),
    frozenset({"great", "good", "nice", "awesome", "cool", "excellent"}),
    frozenset({"you", "u"}),
    frozenset({"your", "ur"}),
    frozenset({"asap", "soon"}),
    frozenset({"regards", "cheers", "best"}),
)


def _style_swap(old: str, new: str) -> bool:
    """Two lower-case forms of the same thing (see SWAP_GROUPS), as the user wrote them."""
    if not (_is_word(old) and _is_word(new) and old == old.lower() and new == new.lower()):
        return False
    return any(old in g and new in g for g in SWAP_GROUPS)


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
        if tag == "replace" and len(old) == 1 and len(new) == 1 and _style_swap(old[0].lower(), new[0].lower()):
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


def _meaning_changed(draft: str, sent: str) -> bool:
    """A small edit that still changes what the email says: a number, a negation or a word swapped
    for another (approve → reject, 5000 → 50000). Such a draft wasn't sent as is."""
    a, b = _tokens(draft), _tokens(sent)
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, [t.lower() for t in a], [t.lower() for t in b]).get_opcodes():
        if tag == "equal":
            continue
        old, new = _expand(a[i1:i2]), _expand(b[j1:j2])
        if old == new:
            continue  # "I'll" → "I will": the same words
        changed = [*old, *new]
        if any(re.search(r"\d", t) or t in _NEGATIONS for t in changed):
            return True
        if tag == "replace" and not (len(old) == len(new) == 1 and _style_swap(old[0], new[0])):
            if any(_is_word(t) for t in changed):
                return True
    return False


_CONTRACTIONS = {
    "i'll": "i will", "we'll": "we will", "you'll": "you will", "it'll": "it will", "i'm": "i am",
    "we're": "we are", "you're": "you are", "they're": "they are", "it's": "it is", "that's": "that is",
    "i've": "i have", "we've": "we have", "i'd": "i would", "we'd": "we would", "let's": "let us",
    "don't": "do not", "doesn't": "does not", "didn't": "did not", "can't": "cannot", "won't": "will not",
    "isn't": "is not", "aren't": "are not", "wasn't": "was not", "shouldn't": "should not",
}  # fmt: skip


def _expand(tokens: list[str]) -> list[str]:
    out: list[str] = []
    for t in tokens:
        out += _CONTRACTIONS.get(t.lower().replace("’", "'"), t.lower()).split()  # noqa: RUF001
    return out


def compare(draft_l1: str, sent_l1: str) -> Comparison:
    # A never-send word shows as [removed] on screen; what the user sends back carries that text.
    draft_l1, sent_l1 = (NEVER_SEND.sub(REMOVED, t) for t in (draft_l1, sent_l1))
    share = edit_share(draft_l1, sent_l1)
    sim = similarity(draft_l1, sent_l1)
    result = outcome_of(share, sim)
    if result == "sent_as_is" and share > 0 and _meaning_changed(draft_l1, sent_l1):
        result = "light_edit"
    return Comparison(
        outcome=result,
        edit_share=share,
        similarity=round(sim, 4),
        draft_words=len(style._words(draft_l1)),
        sent_words=len(style._words(sent_l1)),
        # A rewrite is a different message: nothing in it says how the draft should have been styled.
        edits=[] if result in ("sent_as_is", "rewritten") else style_edits(draft_l1, sent_l1),
    )
