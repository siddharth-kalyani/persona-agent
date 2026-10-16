"""Finding the user's own promises in their sent messages (MVP plan M5, research R05 §5.3).

L1 in, L1 out: the text is already redacted (tokens, slots, never-send placeholders), so nothing
here sees a name or an identifier. Two extractors behind one interface:

  * `OfflineExtractor` — the clearly labelled stand-in until the AWS account exists (founder,
    2026-10-13): first-person future ("I'll send…", "we will revert…", chat's "will share…",
    "sharing mine in 10 mins") with a deliverable verb, never in a question, a condition or a
    negation. Precision first: a missed promise costs less than a ledger full of noise.
  * `BedrockExtractor` (`vanimo/commitments/model.py`) — Claude Haiku with the same output, every
    span checked against the text in code.

Due dates are always resolved here, in code, in the user's time zone (R05 §5.4: model temporal
reasoning is weak): "by Thursday EOD" / "by EOD Friday", "tomorrow", "this week", "12 November",
"in 10 mins". Conventions: a bare weekday that is today means next week's; "next Friday" is the Friday
of next calendar week (Monday to Sunday); "this week" is its Friday (its Sunday when said at the
weekend); "the weekend" is its Saturday; end of day is 18:00.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

from vanimo.learning import labels, style
from vanimo.redaction.marks import L1_MARKS

OFFLINE_LABEL = "Offline stand-in, no AI model: rule-based promise finder"
MAX_PER_ITEM = 5
MAX_WHAT_CHARS = 160


@dataclass(frozen=True)
class Found:
    sentence: str  # L1: the promise as written (a span of the message)
    what: str  # L1: what was promised, short ("Share the final runbook")
    due_phrase: str | None  # L1: as written ("by Thursday EOD")
    due_at: datetime | None  # UTC, resolved in code


class Extractor(Protocol):
    kind: Literal["offline", "bedrock"]

    async def find(self, l1: str, *, made_at: datetime, tz: ZoneInfo) -> list[Found]: ...


# --- sentences ---------------------------------------------------------------------------------
_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def sentences(l1: str) -> list[str]:
    """The message's own sentences, without its greeting and sign-off lines."""
    body = style.body_lines(l1) or l1
    return [s.strip() for s in _SPLIT.split(body) if s and s.strip()]


# --- promises ----------------------------------------------------------------------------------
_VERBS = (
    r"send|share|revert|get\s+back|follow\s+up|update|review|check|confirm|prepare|include|add|fix|deploy|"
    r"schedule|set\s+up|raise|look\s+into|go\s+through|circulate|loop\s+in|arrange|book|call|ping|finish|"
    r"complete|deliver|submit|draft|write|present|provide|publish|upload|mail|email|forward|sort\s+out|"
    r"take\s+care\s+of|organi[sz]e|reply|respond|test|investigate|escalate|chase|connect|introduce|"
    r"walk\s+\S+\s+through|cover|close|clean\s+up|rotate|migrate|merge|release|shortlist|run"
)
_LEAD = (
    r"(?:i|we)\s*['’]ll\s+"  # noqa: RUF001 - both apostrophes
    r"|(?:i|we)\s+(?:will|shall)\s+"
    r"|(?:i\s*['’]?m|i\s+am|we\s*['’]?re|we\s+are)\s+going\s+to\s+"  # noqa: RUF001
    r"|let\s+me\s+"
    r"|will\s+"  # chat: "will share by 5"
)
_PROMISE = re.compile(
    rf"(?:^|[,;:]\s*|\b(?:and|so|then|but|yes|sure|ok|okay|noted)\b[,!]?\s+)"
    rf"(?P<lead>{_LEAD})"
    rf"(?:(?:also|definitely|surely|quickly|then|just|first|try\s+to|try\s+and)\s+)?"
    rf"(?P<what>(?:{_VERBS})\b.*)$",
    re.I,
)
# "sharing mine in 10 mins": a chat promise with a time, no subject.
_GERUND = re.compile(
    r"^(?P<what>(?:sending|sharing|checking|reviewing|updating|fixing|calling|joining|uploading)\b.*?"
    r"\bin\s+(?:an?|\d{1,3})\s*(?:mins?|minutes|hrs?|hours?)\b.*)$",
    re.I,
)
_NEGATION = re.compile(r"\b(?:not|never|no\s+longer|won['’]t|can['’]t|cannot|don['’]t|didn['’]t)\b", re.I)  # noqa: RUF001
_CONDITION = re.compile(r"^(?:if|unless|in\s+case|should\s+you|whenever)\b", re.I)


# --- due dates ---------------------------------------------------------------------------------
_WEEKDAYS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1, "wednesday": 2, "wed": 2, "thursday": 3,
    "thu": 3, "thur": 3, "thurs": 3, "friday": 4, "fri": 4, "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}  # fmt: skip
_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4, "may": 5,
    "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}  # fmt: skip
_WD = "|".join(sorted(_WEEKDAYS, key=len, reverse=True))
_MO = "|".join(sorted(_MONTHS, key=len, reverse=True))
_PART = r"(?:\s+(?P<part>morning|afternoon|evening|night|eod|cob|end\s+of\s+(?:the\s+)?day))?"
_BY = r"(?:(?:by|before|on|till|until|latest\s+by|no\s+later\s+than)\s+)?"
_DUE = re.compile(
    rf"(?P<delta>\bin\s+(?P<n>an?|\d{{1,3}})\s*(?P<unit>mins?|minutes|hrs?|hours?)\b)"
    rf"|(?P<eodday>\b{_BY}(?:eod|cob|end\s+of\s+(?:the\s+)?day)\s+(?:on\s+)?(?P<wd2>{_WD})\b)"
    rf"|(?P<today>\b{_BY}(?:today|tonight|eod|cob|end\s+of\s+(?:the\s+)?day)\b)"
    rf"|(?P<tomorrow>\b{_BY}tomorrow{_PART}\b)"
    rf"|(?P<weekend>\b{_BY}(?:this\s+|the\s+)?weekend\b)"
    rf"|(?P<week>\b{_BY}(?:(?P<which>this|next)\s+week|end\s+of\s+(?:the\s+)?week)\b)"
    rf"|(?P<weekday>\b{_BY}(?P<this>this\s+|next\s+)?(?P<wd>{_WD})\b{_PART.replace('part', 'part2')}\b)"
    rf"|(?P<date>\b{_BY}(?:(?P<d1>\d{{1,2}})(?:st|nd|rd|th)?\s+(?P<m1>{_MO})\b|(?P<m2>{_MO})\s+(?P<d2>\d{{1,2}})"
    rf"(?:st|nd|rd|th)?\b))"
    rf"|(?P<ordinal>\b(?:by|on|before)\s+(?:the\s+)?(?P<d3>\d{{1,2}})(?:st|nd|rd|th)\b)",
    re.I,
)
_TIMES = {"morning": time(12), "afternoon": time(16), "evening": time(20), "night": time(22), "tonight": time(22)}
END_OF_DAY = time(18)


def _at(d: date, t: time, tz: ZoneInfo) -> datetime:
    return datetime.combine(d, t, tzinfo=tz).astimezone(UTC)


def _part(value: str | None) -> time:
    if not value:
        return END_OF_DAY
    return _TIMES.get(value.lower().split()[0], END_OF_DAY)


def due_date(phrase_match: re.Match[str], made_at: datetime, tz: ZoneInfo) -> datetime | None:
    """A due phrase resolved against when the message was sent, in the user's time zone."""
    g = phrase_match.groupdict()
    local = made_at.astimezone(tz)
    today = local.date()
    if g["delta"]:
        n = 1 if g["n"].lower() in ("a", "an") else int(g["n"])
        unit = g["unit"].lower()
        return made_at + (timedelta(hours=n) if unit.startswith(("h",)) else timedelta(minutes=n))
    if g["today"]:
        return _at(today, time(22) if "tonight" in g["today"].lower() else END_OF_DAY, tz)
    if g["tomorrow"]:
        return _at(today + timedelta(days=1), _part(g["part"]), tz)
    monday = today - timedelta(days=today.weekday())
    if g["weekend"]:
        return _at(max(today, monday + timedelta(days=5)), END_OF_DAY, tz)
    if g["week"]:
        if g["which"] and g["which"].lower() == "next":
            return _at(monday + timedelta(days=7 + 4), END_OF_DAY, tz)
        # Said at the weekend, "this week" can only mean what's left of it.
        return _at(monday + timedelta(days=4 if today.weekday() <= 4 else 6), END_OF_DAY, tz)
    if g["eodday"]:
        days = (_WEEKDAYS[g["wd2"].lower()] - today.weekday()) % 7 or 7
        return _at(today + timedelta(days=days), END_OF_DAY, tz)
    if g["weekday"]:
        wd = _WEEKDAYS[g["wd"].lower()]
        prefix = (g["this"] or "").strip().lower()
        if prefix == "next":  # that day of next calendar week
            return _at(monday + timedelta(days=7 + wd), _part(g["part2"]), tz)
        days = (wd - today.weekday()) % 7
        if days == 0 and prefix != "this":
            days = 7
        return _at(today + timedelta(days=days), _part(g["part2"]), tz)
    if g["date"]:
        day = int(g["d1"] or g["d2"])
        month = _MONTHS[(g["m1"] or g["m2"]).lower()]
        for year in (today.year, today.year + 1):
            try:
                d = date(year, month, day)
            except ValueError:
                return None
            if d >= today - timedelta(days=7):
                return _at(d, END_OF_DAY, tz)
        return None
    if g["ordinal"]:
        day = int(g["d3"])
        for months_ahead in (0, 1):
            y, m = (today.year, today.month + months_ahead) if today.month + months_ahead <= 12 else (today.year + 1, 1)
            try:
                d = date(y, m, day)
            except ValueError:
                continue
            if d >= today:
                return _at(d, END_OF_DAY, tz)
        return None
    return None


def find_due(sentence: str, made_at: datetime, tz: ZoneInfo) -> tuple[str | None, datetime | None]:
    masked = L1_MARKS.sub(lambda m: "\x00" * len(m.group()), sentence)  # never a date inside a mark
    m = _DUE.search(masked)
    if not m:
        return None, None
    return sentence[m.start() : m.end()].strip(), due_date(m, made_at, tz)


_NEXT_CLAUSE = re.compile(r"\s*[,;]\s*(?:and|but|so|while|then)\b.*$|\s*;.*$", re.I | re.S)


def _short(what: str, due_phrase: str | None) -> str:
    if due_phrase:
        what = what.replace(due_phrase, " ")
    what = _NEXT_CLAUSE.sub("", what)  # "…, and Vikram will confirm…" is someone else's promise
    what = re.sub(r"\s+([,.;:!?])", r"\1", re.sub(r"\s+", " ", what)).strip(" ,;:.!-")
    what = re.sub(r"\s+(?:and|so|then)$", "", what, flags=re.I)
    if len(what) > MAX_WHAT_CHARS:
        what = what[: MAX_WHAT_CHARS - 1].rsplit(" ", 1)[0] + "…"
    return what[:1].upper() + what[1:]


def promises(l1: str, *, made_at: datetime, tz: ZoneInfo) -> list[Found]:
    out: list[Found] = []
    for s in sentences(l1):
        if s.rstrip().endswith("?") or _CONDITION.match(s) or _NEGATION.search(s):
            continue
        m = _PROMISE.search(s) or _GERUND.match(s)
        if not m:
            continue
        what = m.group("what")
        if len(labels.words(what)) < 2:
            continue  # "will do", "will check": nothing to hold anyone to
        due_phrase, due_at = find_due(s, made_at, tz)
        out.append(Found(sentence=s, what=_short(what, due_phrase), due_phrase=due_phrase, due_at=due_at))
        if len(out) >= MAX_PER_ITEM:
            break
    return out


class OfflineExtractor:
    kind: Literal["offline", "bedrock"] = "offline"

    async def find(self, l1: str, *, made_at: datetime, tz: ZoneInfo) -> list[Found]:
        return promises(l1, made_at=made_at, tz=tz)


# --- "looks done" ------------------------------------------------------------------------------
_DELIVERED = re.compile(
    r"\b(?:pfa|attached|attaching|here\s+is|here['’]s|here\s+are|please\s+find|sharing|shared|sent|done|"  # noqa: RUF001
    r"updated|completed|deployed|fixed|added|included|uploaded|circulated|rotated|merged|released)\b",
    re.I,
)
_STOP = frozenset(
    """with from that this have will your their them they then than what when where which about after before
    also just only into over some more most such very share send revert update review check confirm prepare
    include fix deploy schedule raise circulate arrange book call ping finish complete deliver submit draft
    write present provide publish upload mail email forward reply respond test cover close back follow
    tomorrow today tonight week monday tuesday wednesday thursday friday saturday sunday morning evening""".split()
)


def keywords(l1: str) -> set[str]:
    return {w.lower() for w in labels.words(l1) if len(w) >= 4 and w.lower() not in _STOP}


def looks_done(what: str, later: str) -> bool:
    """A later message of the user's in the same thread or chat delivers it: a delivery word and
    something the promise was about ("PFA the final cutover runbook" for "revert with the final
    runbook"). Only ever a hint: the user confirms."""
    wanted = keywords(what)
    return bool(wanted) and bool(_DELIVERED.search(later)) and bool(wanted & keywords(later))
