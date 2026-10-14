"""S4 deterministic detectors (architecture §7.1-7.2, research doc 10 §6.4).

Tier R — regulated identifiers and secrets: masked irreversibly with a typed slot
("[Aadhaar number]"), never tokenised, never shown to a model. Pattern + checksum/structure
validation + context words, so ordinary numbers aren't flagged.
Tier P — email addresses and phone numbers: found here, tokenised reversibly by the pipeline.

Detection runs on a *shadow copy* with an offset map back to the original (as the never-send
matcher does): NFKC (fullwidth digits/letters, NBSP → space), Devanagari digits → ASCII,
invisible and format characters removed. Numbers are read as digit *groups* separated by up to
two spaces, dots or dashes, and every run of groups is tried as a window, so "2341.2341.2346",
"234 123 412 346", "२३४१ २३४१ २३४६" and "4111 1111 1111 1111" next to a phone number are all found.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from vanimo.redaction import validators as v

Tier = Literal["R", "P"]


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    kind: str  # slot label for Tier R ("Aadhaar number"), token kind for Tier P ("email", "phone")
    tier: Tier


_DEVANAGARI_DIGITS = {0x0966 + i: str(i) for i in range(10)}
_INVISIBLE = frozenset([0x00AD, 0x034F, 0x061C, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x180E, 0x3164, 0xFEFF, 0xFFA0])


def shadow(text: str) -> tuple[str, list[int]]:
    """Normalised copy of `text` and, per shadow character, the index of its source character."""
    out: list[str] = []
    origin: list[int] = []
    for i, ch in enumerate(text):
        if ord(ch) in _INVISIBLE or unicodedata.category(ch) == "Cf":
            continue  # zero-width and bidi controls, tag characters
        for c in unicodedata.normalize("NFKC", ch):
            out.append(_DEVANAGARI_DIGITS.get(ord(c), c))
            origin.append(i)
    return "".join(out), origin


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def _near(text: str, start: int, end: int, words: re.Pattern[str], window: int = 40) -> bool:
    return bool(words.search(text[max(0, start - window) : end + window]))


_ACCOUNT_WORDS = re.compile(r"\b(a/?c|acct|account|bank|iban|beneficiary)\b", re.I)
_ROUTING_WORDS = re.compile(r"\b(routing|aba|rtn|transit)\b", re.I)
_SSN_WORDS = re.compile(r"\b(ssn|social security)\b", re.I)
_EIN_WORDS = re.compile(r"\b(ein|employer identification|tax id|fein)\b", re.I)
_PASSPORT_WORDS = re.compile(r"\bpassport\b", re.I)
_VOTER_WORDS = re.compile(r"\b(voter|epic)\b", re.I)

UPI_HANDLES = (
    "upi|ybl|ibl|axl|apl|okaxis|okhdfcbank|okicici|oksbi|paytm|ptyes|ptsbi|ptaxis|pthdfc|axisbank|"
    "hdfcbank|icici|sbi|kotak|federal|yesbank|idfcbank|indus|freecharge|jupiteraxis|fbl|airtel|"
    "postbank|barodampay|unionbank|cnrb|pnb|boi|aubank|rbl|dbs|hsbc|sc|citi"
)

_ANY = lambda s: True  # noqa: E731

# (pattern, slot label, validator over the match, needs-context pattern or None, value group)
_RULES: list[tuple[re.Pattern[str], str, Callable[[str], bool], re.Pattern[str] | None, int]] = [
    # Secrets and credentials first: they may contain digit runs other rules would split.
    (
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
        "secret",
        _ANY,
        None,
        0,
    ),
    (re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA)[0-9A-Z]{16}\b"), "secret", _ANY, None, 0),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b"), "secret", _ANY, None, 0),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"), "secret", _ANY, None, 0),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"), "secret", _ANY, None, 0),
    (re.compile(r"\bxox[abpr]-[A-Za-z0-9\-]{10,}\b"), "secret", _ANY, None, 0),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "secret", _ANY, None, 0),
    (re.compile(r"\beyJ[\w\-]{10,}\.[\w\-]{10,}\.[\w\-]{10,}\b", re.A), "secret", _ANY, None, 0),
    (re.compile(r"\bBearer\s+([A-Za-z0-9._~+/\-]{20,}=*)"), "secret", _ANY, None, 1),
    # key = value secrets (AWS secret keys, client secrets, API keys, Azure AccountKey, SAS sig).
    (
        re.compile(
            r"\b(?:aws_secret_access_key|secret_access_key|client[_\- ]?secret|secret[_\-]?key|api[_\-]?key|apikey|"
            r"access[_\-]?token|auth[_\-]?token|refresh[_\-]?token|private[_\-]?key|accountkey|sharedaccesskey|"
            r"sig|token)\s*[:=]\s*[\"']?([^\s\"';,&]{8,})",
            re.I,
        ),
        "secret",
        _ANY,
        None,
        1,
    ),
    # Connection strings with a password: scheme://user:PASSWORD@host
    (
        re.compile(
            r"\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|rediss|amqps?|mssql|sqlserver)://[^\s:@/]+:([^\s@/]{3,})@",
            re.I,
        ),
        "secret",
        _ANY,
        None,
        1,
    ),
    # India
    (re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b", re.I), "GSTIN", v.gstin_valid, None, 0),
    (re.compile(r"\b[A-Za-z]{5}\d{4}[A-Za-z]\b"), "PAN", v.pan_valid, None, 0),
    (re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", re.I), "IFSC", v.ifsc_valid, None, 0),
    (re.compile(rf"\b[A-Za-z0-9._\-]{{2,64}}@(?:{UPI_HANDLES})\b(?!\.[A-Za-z])", re.I), "UPI ID", _ANY, None, 0),
    (re.compile(r"\b[A-Z]{3}\d{7}\b", re.I), "voter ID", _ANY, _VOTER_WORDS, 0),
    (re.compile(r"\b[A-Z][0-9]{7}\b", re.I), "passport number", _ANY, _PASSPORT_WORDS, 0),
]

# Digit groups: up to two separators (space, dot, dash, tab) between groups.
_DIGIT_RUN = re.compile(r"(?<![\w])\d+(?:[ .\-\t]{1,2}\d+)*(?![\w])")
_GROUP = re.compile(r"\d+")

# "password: X", "pwd is X", "passcode = X" → mask the value only.
_PASSWORD = re.compile(
    r"\b(password|passwd|pwd|passcode|pin)\b"
    r"(\s+(?:is|was|=)\s+(?:(?:still|now|currently|just|set\s+to|changed\s+to)\s+)?|\s*[:=]\s*)"
    r"(?!(?:still|now|currently|just|set|changed|policy|reset|expired?)\b)(\S{3,63}[^\s.,;:!?)\]'\"])",
    re.I,
)

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9\-]{1,63}(?:\.[A-Za-z0-9\-]{1,63})+\b")
_PHONE = re.compile(
    r"(?<![\w+])(?:\+91[ \-]?|0)?[6-9]\d{4}[ \-]?\d{5}(?!\w)"  # India mobile
    r"|(?<![\w+])\+?1?[ \-.]?\(?[2-9]\d{2}\)?[ \-.]\d{3}[ \-.]\d{4}(?!\w)"  # US/NANP
    r"|(?<![\w+])\+\d{1,3}[ \-]?\d{2,4}[ \-]?\d{3,4}[ \-]?\d{3,4}(?!\w)"  # other international
)
# Long random-looking strings (keys, tokens) with mixed case and digits.
_RANDOM = re.compile(r"(?<![\w+/\-])[A-Za-z0-9+_\-]{32,}={0,2}(?![\w+/\-])")


def _entropy(s: str) -> float:
    counts = Counter(s)
    return -sum(n / len(s) * math.log2(n / len(s)) for n in counts.values())


def _random_secret(s: str) -> bool:
    core = s.rstrip("=")
    return (
        any(c.isupper() for c in core)
        and any(c.islower() for c in core)
        and any(c.isdigit() for c in core)
        and _entropy(core) >= 4.2
    )


def _classify_number(digits: str, sh: str, start: int, end: int, *, plus: bool, dashed_ssn: bool) -> str | None:
    """Slot label for a window of digit groups, or None."""
    n = len(digits)
    if n == 12 and not plus and v.aadhaar_valid(digits):
        return "Aadhaar number"
    if 13 <= n <= 19 and v.card_valid(digits):
        return "card number"
    if n == 16 and v.verhoeff_valid(digits):
        return "Aadhaar VID"
    if n == 9:
        if (dashed_ssn or _near(sh, start, end, _SSN_WORDS)) and (v.ssn_valid(digits) or v.itin_valid(digits)):
            return "SSN"
        if _near(sh, start, end, _EIN_WORDS) and v.ein_valid(digits):
            return "EIN"
        if _near(sh, start, end, _ROUTING_WORDS) and v.aba_valid(digits):
            return "routing number"
    if 9 <= n <= 18 and _near(sh, start, end, _ACCOUNT_WORDS):
        return "bank account"
    return None


def _numbers(sh: str, taken: list[tuple[int, int]]) -> list[tuple[int, int, str]]:
    """Regulated numbers among runs of digit groups: every window of consecutive groups is tried,
    longest valid windows win (so a card next to a phone number is still found)."""
    out: list[tuple[int, int, str]] = []
    for run in _DIGIT_RUN.finditer(sh):
        groups = [(run.start() + g.start(), run.start() + g.end()) for g in _GROUP.finditer(run.group())]
        candidates: list[tuple[int, int, int, str]] = []
        for i in range(len(groups)):
            total = 0
            for j in range(i, len(groups)):
                total += groups[j][1] - groups[j][0]
                if total > 19:
                    break
                if total < 9:
                    continue
                s, e = groups[i][0], groups[j][1]
                text = sh[s:e]
                kind = _classify_number(
                    _digits(text),
                    sh,
                    s,
                    e,
                    plus=s > 0 and sh[s - 1] == "+",
                    dashed_ssn=bool(re.fullmatch(r"\d{3}[\- ]\d{2}[\- ]\d{4}", text)),
                )
                if kind:
                    candidates.append((e - s, s, e, kind))
        for _, s, e, kind in sorted(candidates, reverse=True):
            if all(e <= ts or s >= te for ts, te in taken):
                taken.append((s, e))
                out.append((s, e, kind))
    return out


def detect(text: str) -> list[Span]:
    """All Tier R and Tier P spans in `text` (offsets into the original), non-overlapping."""
    sh, origin = shadow(text)
    found: list[tuple[int, int, str, Tier]] = []  # shadow offsets

    def free(s: int, e: int) -> bool:
        return all(e <= f[0] or s >= f[1] for f in found)

    for m in _PASSWORD.finditer(sh):
        found.append((m.start(3), m.end(3), "password", "R"))
    for pattern, kind, ok, context, group in _RULES:
        for m in pattern.finditer(sh):
            s, e = m.span(group)
            if not free(s, e):
                continue
            if context is not None and not _near(sh, s, e, context):
                continue
            if ok(m.group(group)):
                found.append((s, e, kind, "R"))
    taken = [(f[0], f[1]) for f in found]
    found += [(s, e, kind, "R") for s, e, kind in _numbers(sh, taken)]
    for m in _RANDOM.finditer(sh):
        if free(*m.span()) and _random_secret(m.group()):
            found.append((m.start(), m.end(), "secret", "R"))
    for m in _EMAIL.finditer(sh):
        if free(*m.span()):
            found.append((m.start(), m.end(), "email", "P"))
    for m in _PHONE.finditer(sh):
        if free(*m.span()) and len(_digits(m.group())) >= 10:
            found.append((m.start(), m.end(), "phone", "P"))
    spans = [Span(origin[s], origin[e - 1] + 1, kind, tier) for s, e, kind, tier in found if e > s]
    return sorted(spans, key=lambda f: f.start)


def tier_r_residue(text: str) -> list[str]:
    """Kinds of any Tier R identifiers still present (S9 verify). Slot labels like
    "[Aadhaar number]" don't match the patterns, so a clean L1 text returns []."""
    return [s.kind for s in detect(text) if s.tier == "R"]
