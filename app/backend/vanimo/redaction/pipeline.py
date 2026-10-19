"""L0 → L1 redaction (architecture §7.2 S2-S9), in memory only.

    S2   parse: Unicode tag characters removed, hidden HTML already dropped by the source
    S2.5 never-send words → ⟦NS_…⟧ placeholders (user's matcher)          fail-closed
    S4   Tier R (regulated identifiers, secrets) → typed slots "[PAN]"     fail-closed
    S5   names from the M365 header/directory gazetteer → person tokens
    S5   PII backstop (F11): Amazon Comprehend (or its offline stand-in) on the text so far; names it
         finds → person tokens, contact details → tokens, identifiers and addresses → slots
                                                                            fail-closed
    S8   names, email addresses, phone numbers → reversible tokens
    S9   verify: detectors re-run on the output; any Tier R, never-send, address, phone or
         gazetteer-name residue blocks the item                           fail-closed

Tokens are deterministic per tenant (an HMAC of the identifier), so the same colleague is the
same token across messages and style learning keeps structure (§7.3). Name form is part of
the token (`⟦PERSON_3fa2c1d0⟧` first name, `.full`, `.last`) and honorifics stay outside it
("Meera-ji" → "⟦PERSON_…⟧-ji"). The user's own name becomes ⟦ME⟧ so sign-offs are learnable.
The token → value map is returned to the caller to store encrypted for the owner's display.

The NER ensemble (Presidio/GLiNER/IndicNER, S5) and the contextual Tier C/S classifier (S6)
are not in the MVP: the gazetteer of known participants is the main name source, and the S5
backstop (Comprehend, F11) catches names that never appear in a header or the directory. The
backstop sees only text our own stages already masked. If it can't be reached, the item is
blocked with `BackstopUnavailable` (a `RedactionBlocked`): jobs stop and retry rather than skip.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from vanimo.backstops.pii import ACTIONS, Finding, PiiDetector, PiiUnavailable, wanted
from vanimo.controls.neversend import Matcher
from vanimo.redaction import detectors
from vanimo.redaction.marks import L1_MARKS, SLOT, TOKEN
from vanimo.redaction.parse import clean

__all__ = [
    "SLOT",
    "TOKEN",
    "BackstopUnavailable",
    "Gazetteer",
    "Person",
    "Redacted",
    "RedactionBlocked",
    "Redactor",
    "rehydrate",
]
_HONORIFIC_TAIL = ("ji", "jee", "bhai", "sahab", "saheb")
_NAME_STOP = frozenset({"team", "all", "sir", "madam", "dear", "hi", "hello", "thanks", "regards", "best", "the"})
# Titles in directory display names ("Dr. Anil Kumar", "Shri R. K. Sharma"): never a name form.
_TITLES = frozenset(
    "dr mr mrs ms miss mx prof sir shri sri smt shrimati kumari km er ca adv capt col maj gen lt cdr".split()
)
# Names that are also everyday English words match only when capitalised as a name.
_WORD_NAMES = frozenset(
    "will mark grace hope joy rose may june bill pat sunny dawn faith art guy rich chase hunter summer "
    "autumn amber ruby crystal ray page lane holly ivy iris angel honey sky rain chip max norm rob sue "
    "don gene earl frank victor win sandy cliff dean drew glen gay hazel jack jean kit lily miles "
    "neil penny rusty sterling wade wolf young asha prem raja".split()
)


class RedactionBlocked(Exception):
    """The item must not be stored or shown to a model. `reason` is content-free."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class BackstopUnavailable(RedactionBlocked):
    """The S5 backstop couldn't be reached. The item is blocked like any other; a job reading many
    items stops instead of skipping them (it retries later, nothing is lost or marked done)."""

    code = "pii_backstop_unavailable"  # a failed run's error code

    def __init__(self) -> None:
        super().__init__("pii_backstop_unavailable")


@dataclass(frozen=True)
class Person:
    full_name: str
    email: str | None = None


@dataclass
class Gazetteer:
    """Names known from message headers, the directory (manager, reports) and the user's profile."""

    me: Person | None = None
    people: list[Person] = field(default_factory=list)

    def add(self, name: str | None, email: str | None = None) -> None:
        if not name or "@" in name:
            return
        name = " ".join(name.split())
        if len(name) < 2:
            return
        if self.me and email and self.me.email and email.lower() == self.me.email.lower():
            return
        if any(p.full_name.casefold() == name.casefold() for p in self.people):
            return
        self.people.append(Person(name, email.lower() if email else None))


@dataclass
class Redacted:
    text: str
    tokens: dict[str, tuple[str, str]]  # token → (kind, original value); stored encrypted by the caller
    counts: dict[str, int]  # content-free: kind → number of spans masked
    suspicious: bool = False  # Unicode tag characters or hidden HTML were present


Hasher = Callable[[str, str], str]  # (kind, normalised value) → hex digest


def _fold(s: str) -> str:
    return unicodedata.normalize("NFKC", s).casefold()


def _name_parts(full_name: str) -> list[str]:
    """The words of a name without titles and initials ("Dr. R. Anil Kumar" → Anil, Kumar).
    Directory forms are normalised: "Iyer, Meera" → Meera Iyer; "(Contractor)" and similar dropped."""
    name = re.sub(r"\s*[(\[][^)\]]*[)\]]", " ", full_name).strip()
    if name.count(",") == 1:
        last, first = (x.strip() for x in name.split(","))
        name = f"{first} {last}" if first and last else name.replace(",", " ")
    words = [w.strip(",;") for w in re.split(r"\s+", name) if w.strip(",;")]
    return [w for w in words if _fold(w).rstrip(".") not in _TITLES and not re.fullmatch(r"\w\.?", w)]


class Redactor:
    """One user's redactor: their never-send matcher, gazetteer and token hasher."""

    def __init__(
        self,
        matcher: Matcher,
        gazetteer: Gazetteer,
        hasher: Hasher,
        *,
        pii: PiiDetector | None = None,
        pii_scope: str | None = None,
    ) -> None:
        self.matcher = matcher
        self.hasher = hasher
        # F12: names are replaced only if the user chose it (Learning page). Off: no gazetteer names, no
        # backstop NAME findings, no name residue check; tokens still serve greetings and sign-offs.
        self.redact_names = getattr(matcher, "redact_names", True)
        self._names = self._name_patterns(gazetteer) if self.redact_names else []
        if pii is None:  # the process's backstop (vanimo.backstops): never skipped by omission
            from vanimo.backstops import current

            b = current()
            pii, pii_scope = b.pii, pii_scope or b.comprehend_scope
        self.pii = pii
        self.pii_scope = pii_scope or "all"

    # --- tokens -------------------------------------------------------------------------------
    def _token(self, kind: str, value: str) -> str:
        return self.hasher(kind, value)[:8]

    def person_base(self, person: Person, *, me: bool = False) -> str:
        """A person's token stem ("⟦PERSON_3fa2c1d0" or "⟦ME"): add "⟧" (first name), ".full⟧" or ".last⟧".
        The same stem the learner gives them, so live text and learned text agree."""
        return "⟦ME" if me else f"⟦PERSON_{self._token('person', person.email or _fold(person.full_name))}"

    def person_forms(self, person: Person, *, me: bool = False) -> dict[str, tuple[str, str]]:
        """{"full" | "first" | "last": (token, surface)} for writing to someone (greetings, sign-offs)."""
        base = self.person_base(person, me=me)
        parts = _name_parts(person.full_name)
        out = {"full": (base + ".full⟧", " ".join(parts) or person.full_name)}
        if parts:
            out["first"] = (base + "⟧", parts[0])
        if len(parts) >= 2:
            out["last"] = (base + ".last⟧", parts[-1])
        return out

    def email_token(self, email: str) -> str:
        return f"⟦EMAIL_{self._token('email', email.lower())}⟧"

    def _name_patterns(self, g: Gazetteer) -> list[tuple[re.Pattern[str], str, str]]:
        """(pattern, token, original form) — longest forms first, so full names win."""
        forms: list[tuple[str, str]] = []  # (surface form, token)
        first_seen: dict[str, str] = {}
        everyone = ([(g.me, True)] if g.me else []) + [(p, False) for p in g.people]
        for person, is_me in everyone:
            base = self.person_base(person, me=is_me)
            forms.append((person.full_name, base + ".full⟧"))
            parts = _name_parts(person.full_name)
            if len(parts) >= 2 and " ".join(parts) != person.full_name:
                forms.append((" ".join(parts), base + ".full⟧"))
            if len(parts) >= 2:
                last = parts[-1]
                if len(last) >= 2 and _fold(last) not in _NAME_STOP:
                    forms.append((last, base + ".last⟧"))
            first = parts[0] if parts else ""
            # An ambiguous first name stays with the first person seen (the user, then header order).
            if len(first) >= 2 and _fold(first) not in _NAME_STOP and _fold(first) not in first_seen:
                first_seen[_fold(first)] = base
                forms.append((first, base + "⟧"))
        forms.sort(key=lambda f: -len(f[0]))
        out = []
        seen: set[str] = set()
        for surface, token in forms:
            if _fold(surface) in seen:
                continue
            seen.add(_fold(surface))
            words = [re.escape(w) for w in surface.split()]
            body = r"[\s\-]+".join(words)
            # Word-bounded; a glued honorific ("Meeraji") or possessive stays outside the token.
            tail = "|".join(_HONORIFIC_TAIL)
            # Short single names ("Rao", "Om") and names that are also English words ("Will")
            # match only when written with a capital, as names are.
            short = " " not in surface and (len(surface) <= 3 or _fold(surface) in _WORD_NAMES)
            flags = 0 if short else re.I
            pat = re.compile(rf"(?<![\w⟦]){body}(?=(?:{tail})?(?:'s|’s)?(?!\w))", flags)  # noqa: RUF001
            out.append((pat, token, surface))
        return out

    # --- pipeline -----------------------------------------------------------------------------
    async def redact(self, text: str | None, *, hidden_seen: bool = False) -> Redacted:
        if not text:
            return Redacted("", {}, {})
        body, tokens, counts, had_tags = self._local(text)
        suspicious = had_tags or hidden_seen

        # S5 backstop: a second detector on what our own stages left (fail-closed).
        if self._wants_backstop(counts, suspicious):
            try:
                findings = await self.pii.detect(body)
            except PiiUnavailable:
                raise BackstopUnavailable() from None
            except Exception as exc:
                raise BackstopUnavailable() from exc
            body = self._apply_findings(body, findings, tokens, counts)

        self.verify(body)
        return Redacted(body, tokens, counts, suspicious=suspicious)

    def _wants_backstop(self, counts: dict[str, int], suspicious: bool) -> bool:
        """ "all": every item. "flagged" (the production rule, architecture §7.2 S5): only items our
        detectors found regulated identifiers or hidden content in."""
        if self.pii_scope == "all":
            return True
        return suspicious or any(k not in ("email", "phone", "name", "never_send") for k in counts)

    def _local(self, text: str) -> tuple[str, dict[str, tuple[str, str]], dict[str, int], bool]:
        """S2-S5 (gazetteer) in our own code: (text so far, tokens, counts, tag characters seen)."""
        counts: dict[str, int] = {}
        tokens: dict[str, tuple[str, str]] = {}

        # S2: invisible tag characters (a smuggling channel to models) removed. ⟦ and ⟧ are
        # reserved for Vanimo's own marks, so any in the input become plain brackets: a sender
        # can't hide a value from the detectors, or plant a token, by wrapping it in ⟦…⟧.
        body, had_tags = clean(text)
        body = unicodedata.normalize("NFC", body).replace("⟦", "[").replace("⟧", "]")

        # S2.5: never-send words first, before anything else sees the text.
        try:
            body, ns_hits = self.matcher.mask(body)
        except Exception as exc:
            raise RedactionBlocked("never_send_error") from exc
        body = body or ""
        if ns_hits:
            counts["never_send"] = ns_hits

        # S4: Tier R → irreversible typed slots; Tier P (emails, phones) → tokens.
        try:
            spans = detectors.detect(body)
        except Exception as exc:
            raise RedactionBlocked("detector_error") from exc
        out: list[str] = []
        pos = 0
        for s in spans:
            if _inside_token(body, s.start, s.end):
                continue
            out.append(body[pos : s.start])
            value = body[s.start : s.end]
            if s.tier == "R":
                out.append(f"[{s.kind}]")
            else:
                key = value.lower() if s.kind == "email" else re.sub(r"\D", "", value)[-10:]
                tok = f"⟦{s.kind.upper()}_{self._token(s.kind, key)}⟧"
                tokens[tok] = (s.kind, value)
                out.append(tok)
            counts[s.kind] = counts.get(s.kind, 0) + 1
            pos = s.end
        out.append(body[pos:])
        body = "".join(out)

        # S5/S8: gazetteer names → person tokens.
        for pat, tok, surface in self._names:
            body, n = _sub_outside_tokens(pat, tok, body)
            if n:
                tokens[tok] = ("person", surface)
                counts["name"] = counts.get("name", 0) + n
        return body, tokens, counts, had_tags

    def _apply_findings(
        self, body: str, findings: Iterable[Finding], tokens: dict[str, tuple[str, str]], counts: dict[str, int]
    ) -> str:
        """Backstop findings (offsets into `body`) masked like our own: never inside a mark, never
        overlapping each other (the longest finding at a position wins)."""
        marks = [(m.start(), m.end()) for m in L1_MARKS.finditer(body)]
        pieces: list[tuple[int, int, str, str]] = []  # (start, end, replacement, count kind)
        keep = [f for f in findings if wanted(f) and (self.redact_names or f.type != "NAME")]
        for f in sorted(keep, key=lambda f: (f.start, f.start - f.end)):
            if not 0 <= f.start < f.end <= len(body):
                continue
            what, label = ACTIONS[f.type]
            for s, e in _outside(f.start, f.end, marks):
                s, e = _trim(body, s, e)
                if what == "person":
                    e = s + len(_without_honorific(body[s:e]))
                if e <= s or not re.search(r"\w", body[s:e]) or any(ps < e and s < pe for ps, pe, _, _ in pieces):
                    continue
                value = body[s:e]
                if what == "slot":
                    repl = f"[{label}]"
                elif what == "person":
                    parts = _name_parts(value) or value.split()
                    repl = self.person_base(Person(" ".join(parts))) + (".full⟧" if len(parts) >= 2 else "⟧")
                    tokens[repl] = ("person", value)
                else:
                    key = value.lower() if what == "email" else (re.sub(r"\D", "", value)[-10:] or _fold(value))
                    repl = f"⟦{what.upper()}_{self._token(what, key)}⟧"
                    tokens[repl] = (what, value)
                pieces.append((s, e, repl, label))
        if not pieces:
            return body
        out: list[str] = []
        pos = 0
        for s, e, repl, label in sorted(pieces):
            out += [body[pos:s], repl]
            pos = e
            counts[label] = counts.get(label, 0) + 1
        out.append(body[pos:])
        counts["s5_backstop"] = counts.get("s5_backstop", 0) + len(pieces)
        return "".join(out)

    def verify(self, l1: str) -> None:
        """S9: the output must hold no Tier R value, never-send word, address, phone or known name."""
        try:
            residue = [s.kind for s in detectors.detect(_strip_tokens(l1))]
            ns = self.matcher.count(l1, opaque=L1_MARKS)
            names = sum(1 for pat, _, _ in self._names if pat.search(_strip_tokens(l1)))
        except Exception as exc:
            raise RedactionBlocked("verify_error") from exc
        if residue:
            tier_r = any(k not in ("email", "phone") for k in residue)
            raise RedactionBlocked("residue_tier_r" if tier_r else "residue_tier_p")
        if ns:
            raise RedactionBlocked("residue_never_send")
        if names:
            raise RedactionBlocked("residue_name")

    async def redact_many(self, texts: Iterable[str | None]) -> list[Redacted]:
        return [await self.redact(t) for t in texts]


def _outside(start: int, end: int, marks: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """The parts of [start, end) not covered by a mark."""
    out: list[tuple[int, int]] = []
    pos = start
    for ms, me in marks:
        if me <= pos or ms >= end:
            continue
        if ms > pos:
            out.append((pos, ms))
        pos = max(pos, me)
    if pos < end:
        out.append((pos, end))
    return out


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and (text[start].isspace() or text[start] in ",;:"):
        start += 1
    while end > start and (text[end - 1].isspace() or text[end - 1] in ",;:"):
        end -= 1
    return start, end


def _without_honorific(name: str) -> str:
    """ "Meera-ji" → "Meera": an honorific stays outside a person token, as for gazetteer names."""
    tail = "|".join(_HONORIFIC_TAIL)
    m = re.fullmatch(rf"(.*\w)[\s\-](?:{tail})", name, re.I)
    return m.group(1) if m else name


def _inside_token(text: str, start: int, end: int) -> bool:
    return any(m.start() < end and start < m.end() for m in L1_MARKS.finditer(text))


def _strip_tokens(text: str) -> str:
    """Tokens, placeholders and slots replaced by a neutral space, so verification looks only at
    free text. Only Vanimo's own marks match (S2 removed every ⟦ ⟧ from the input)."""
    return L1_MARKS.sub(" ", text)


def _sub_outside_tokens(pat: re.Pattern[str], repl: str, text: str) -> tuple[str, int]:
    marks = [(m.start(), m.end()) for m in L1_MARKS.finditer(text)]
    n = 0

    def _r(m: re.Match[str]) -> str:
        nonlocal n
        if any(ms < m.end() and m.start() < me for ms, me in marks):
            return m.group()
        n += 1
        return repl

    return pat.sub(_r, text), n


def rehydrate(l1: str, tokens: dict[str, str], *, allowed: set[str] | None = None) -> str:
    """Display path for the owner: tokens present in `tokens` (and `allowed`, if given — the
    token-spoofing defence of §7.3) become their values; never-send placeholders show [removed]."""
    from vanimo.controls.neversend import render_removed

    def _r(m: re.Match[str]) -> str:
        t = m.group()
        if allowed is not None and t not in allowed:
            return t
        return tokens.get(t, t)

    return render_removed(TOKEN.sub(_r, l1)) or ""
