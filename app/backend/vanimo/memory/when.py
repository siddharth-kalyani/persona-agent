"""When a question is about, resolved in code (research R05 §5.4: model temporal reasoning is weak).

"today", "yesterday", "on Tuesday" / "Tuesday's" / "last Tuesday", "this week", "last week",
"this month", "last month", "3 days ago", "past 2 weeks", "14 Oct" / "October 14th", parts of a day
("this morning", "yesterday afternoon") and clock times ("at 4", "4 pm", "16:30", "noon"). A bare
hour from 1 to 7 is the afternoon (working hours). All in the cell's time zone.

`at` is a clock time the question named: "the 4 pm meeting" is then the meeting starting nearest
to it (the caller decides, and asks when two are equally near).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_WD = {d: i for i, d in enumerate(_WEEKDAYS)} | {d[:3]: i for i, d in enumerate(_WEEKDAYS)} | {"tues": 1, "thurs": 3}
_MONTHS = {
    m: i + 1
    for i, m in enumerate(
        [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ]
    )
}
_MON = {**_MONTHS, **{m[:3]: n for m, n in _MONTHS.items()}, "sept": 9}
_PARTS = {"morning": (time(8), time(12)), "afternoon": (time(12), time(17)), "evening": (time(17), time(21))}
_WD_RE = "|".join(sorted(_WD, key=len, reverse=True))
_MON_RE = "|".join(sorted(_MON, key=len, reverse=True))
_DAY_OF = re.compile(rf"\b(?:(?P<last>last|this|on|past)\s+)?(?P<wd>{_WD_RE})(?:['’]s)?\b", re.I)  # noqa: RUF001
_DATE_DM = re.compile(rf"\b(?P<d>\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?(?P<m>{_MON_RE})\b", re.I)
_DATE_MD = re.compile(rf"\b(?P<m>{_MON_RE})\s+(?P<d>\d{{1,2}})(?:st|nd|rd|th)?\b", re.I)
_AGO = re.compile(r"\b(?P<n>\d{1,2}|a|one|two|three)\s+(?P<u>days?|weeks?)\s+ago\b", re.I)
_PAST = re.compile(r"\b(?:last|past)\s+(?P<n>\d{1,2}|two|three|few)\s+(?P<u>days|weeks)\b", re.I)
_CLOCK = re.compile(
    r"\b(?:at\s+)?(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ap>a\.?m\.?|p\.?m\.?)(?!\w)"
    r"|\bat\s+(?P<h2>\d{1,2})(?::(?P<m2>\d{2}))?\b(?!\s*(?:days?|weeks?|%))"
    r"|\b(?P<h3>[01]?\d|2[0-3]):(?P<m3>[0-5]\d)\b"
    r"|\b(?P<noon>noon|midday)\b",
    re.I,
)
_PART = re.compile(r"\b(?P<this>this\s+)?(?P<part>morning|afternoon|evening)\b", re.I)
_WORDS = {"a": 1, "one": 1, "two": 2, "three": 3, "few": 3}


@dataclass(frozen=True)
class When:
    start: datetime  # aware
    end: datetime
    at: time | None  # a clock time named in the question
    day: date | None  # a single day named in the question
    explicit: bool  # the question named a time at all
    label: str


def _bounds(d0: date, d1: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    return datetime.combine(d0, time(0), tz), datetime.combine(d1 + timedelta(days=1), time(0), tz)


def clock(question: str) -> time | None:
    m = _CLOCK.search(question)
    if not m:
        return None
    if m.group("noon"):
        return time(12)
    if m.group("h"):
        h, mi, ap = int(m.group("h")), int(m.group("m") or 0), m.group("ap").lower()[0]
        if not 1 <= h <= 12:
            return None
        h = (h % 12) + (12 if ap == "p" else 0)
    elif m.group("h2"):
        h, mi = int(m.group("h2")), int(m.group("m2") or 0)
        if h > 23:
            return None
        if 1 <= h <= 7:
            h += 12  # "at 4" in a work question is 4 pm
    else:
        h, mi = int(m.group("h3")), int(m.group("m3"))
    return time(h, mi) if mi < 60 else None


def resolve(question: str, now: datetime, tz: ZoneInfo, *, lookback: timedelta) -> When:
    q = question.lower()
    local = now.astimezone(tz)
    today = local.date()
    at = clock(q)
    part = _PART.search(q)
    day: date | None = None
    span: tuple[date, date] | None = None
    label = ""

    if "day before yesterday" in q:
        day, label = today - timedelta(days=2), "the day before yesterday"
    elif re.search(r"\byesterday\b", q):
        day, label = today - timedelta(days=1), "yesterday"
    elif re.search(r"\b(?:today|this\s+(?:morning|afternoon|evening))\b", q):
        day, label = today, "today"
    elif re.search(r"\blast\s+week\b", q):
        monday = today - timedelta(days=today.weekday() + 7)
        span, label = (monday, monday + timedelta(days=6)), "last week"
    elif re.search(r"\bthis\s+week\b", q):
        span, label = (today - timedelta(days=today.weekday()), today), "this week"
    elif re.search(r"\blast\s+month\b", q):
        first = today.replace(day=1)
        prev_last = first - timedelta(days=1)
        span, label = (prev_last.replace(day=1), prev_last), "last month"
    elif re.search(r"\bthis\s+month\b", q):
        span, label = (today.replace(day=1), today), "this month"
    elif m := _AGO.search(q):
        n = int(m.group("n")) if m.group("n").isdigit() else _WORDS[m.group("n").lower()]
        delta = timedelta(days=n * (7 if m.group("u").startswith("week") else 1))
        if m.group("u").startswith("week"):
            span, label = (today - delta - timedelta(days=3), today - delta + timedelta(days=3)), m.group(0)
        else:
            day, label = today - delta, m.group(0)
    elif m := _PAST.search(q):
        n = int(m.group("n")) if m.group("n").isdigit() else _WORDS[m.group("n").lower()]
        days = n * (7 if m.group("u").startswith("week") else 1)
        span, label = (today - timedelta(days=days), today), m.group(0)
    elif (m := _DATE_DM.search(q)) or (m := _DATE_MD.search(q)):
        month, d = _MON[m.group("m").lower()], int(m.group("d"))
        try:
            day = date(today.year, month, d)
            if day > today:
                day = date(today.year - 1, month, d)
            label = day.strftime("%d %b")
        except ValueError:
            day = None
    elif m := _DAY_OF.search(q):
        wd = _WD[m.group("wd").lower()]
        back = (today.weekday() - wd) % 7
        if m.group("last") and m.group("last").lower() == "last" and back == 0:
            back = 7
        day, label = today - timedelta(days=back), _WEEKDAYS[wd].capitalize()

    if day is not None:
        start, end = _bounds(day, day, tz)
        if part:
            p0, p1 = _PARTS[part.group("part").lower()]
            start, end = datetime.combine(day, p0, tz), datetime.combine(day, p1, tz)
            label = f"{label} {part.group('part').lower()}".strip()
        if at is not None:
            label = f"{label} at {at.strftime('%H:%M')}".strip()
        return When(start, end, at, day, True, label)
    if span is not None:
        start, end = _bounds(span[0], span[1], tz)
        return When(start, end, at, None, True, label)
    if part is not None and part.group("this"):
        p0, p1 = _PARTS[part.group("part").lower()]
        return When(datetime.combine(today, p0, tz), datetime.combine(today, p1, tz), at, today, True, part.group(0))
    start = (local - lookback).replace(hour=0, minute=0, second=0, microsecond=0)
    if at is not None:
        return When(start, local + timedelta(minutes=1), at, None, True, f"at {at.strftime('%H:%M')}")
    return When(start, local + timedelta(minutes=1), None, None, False, "")
