"""Live context for one draft (architecture §7.2 S12, §6.5 X2 and X6), in memory only.

Order, as for learning:
  1. thread headers only (metadata) → the exclusion engine decides on the whole conversation:
     its thread rule, everyone in it and everyone being written to;
  2. an excluded conversation is refused — a user rule allows a one-off draft that is never
     stored, an organisation rule never does;
  3. only then are the last few messages' own words fetched and redacted to L1 (never-send →
     Tier R slots → name, address and phone tokens → verify, fail-closed).

The user's instruction and subject go through the same redaction. The token → value map lives
only in this request, for re-hydrating the draft on the owner's screen.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from vanimo.controls.engine import Decision, ExclusionEngine
from vanimo.controls.neversend import Matcher
from vanimo.learning import labels
from vanimo.redaction.parse import strip_quotes, strip_signature_noise
from vanimo.redaction.pipeline import Gazetteer, Hasher, Person, Redacted, RedactionBlocked, Redactor
from vanimo.sources.base import Address, MessageHeader, WorkspaceSource

MAX_THREAD_MESSAGES = 4  # the most recent messages of the thread given to the drafter
MAX_MESSAGE_CHARS = 4000  # per message, before redaction (denial of wallet)
MAX_RECIPIENTS = 50
DIRECTORY_TTL_S = 600.0

Mode = Literal["reply", "new"]


class DraftError(Exception):
    """A draft can't be made. `code` and `extra` are content-free and go back to the client."""

    def __init__(self, code: str, status: int = 409, **extra: object) -> None:
        super().__init__(code)
        self.code = code
        self.status = status
        self.extra = extra


# --- directory -------------------------------------------------------------------------------
@dataclass(frozen=True)
class Directory:
    me: Person
    manager: str | None
    reports: frozenset[str]
    org_domains: frozenset[str]
    people: tuple[Person, ...]  # the manager and reports, for the gazetteer


class DirectoryCache:
    """Profile, manager, reports and the organisation's domains change rarely: cached per user for
    10 minutes so a draft costs no extra Graph calls for them (in-process, one API task)."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, str], tuple[float, Directory]] = {}

    async def get(self, key: tuple[str, str], source: WorkspaceSource, self_email: str) -> Directory:
        hit = self._items.get(key)
        if hit and time.monotonic() - hit[0] < DIRECTORY_TTL_S:
            return hit[1]
        profile, manager, reports, domains = await asyncio.gather(
            source.profile(), source.manager(), source.direct_reports(), source.org_domains()
        )
        people = [Person(manager.display_name, manager.email)] if manager and manager.display_name else []
        people += [Person(r.name, r.email.lower()) for r in reports if r.name]
        directory = Directory(
            me=Person(profile.display_name or self_email.split("@")[0], self_email),
            manager=((manager.email or "").lower() or None) if manager else None,
            reports=frozenset(r.email.lower() for r in reports),
            org_domains=frozenset(domains),
            people=tuple(people),
        )
        if len(self._items) > 5000:
            self._items.clear()
        self._items[key] = (time.monotonic(), directory)
        return directory


class DraftThrottle:
    """Per-user sliding windows (in-process: one API task in the MVP)."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, *, per_minute: int, per_day: int) -> None:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > 86_400:
            hits.popleft()
        if len(hits) >= per_day or sum(1 for h in hits if now - h <= 60) >= per_minute:
            raise DraftError("too_many_drafts", 429)
        hits.append(now)
        if len(self._hits) > 10_000:
            for stale in list(self._hits)[:1000]:
                del self._hits[stale]


# --- audience --------------------------------------------------------------------------------
@dataclass(frozen=True)
class Recipient:
    address: Address
    forms: dict[str, tuple[str, str]]  # Redactor.person_forms: form → (token, name); empty without a name
    token: str  # how the prompt refers to them: their full-name token, or their address token


@dataclass
class Audience:
    relationship: labels.Relationship
    to: list[Recipient]
    cc: list[Recipient]
    internal: int
    external: int

    @property
    def label(self) -> str:
        n = len(self.to) + len(self.cc)
        plural = n > 1
        return {
            "manager": "your manager" + (" and others" if plural else ""),
            "report": "your direct reports" if plural else "your direct report",
            "peer": "colleagues" if plural else "a colleague",
            "external": "people outside your organisation" if plural else "someone outside your organisation",
            "personal": "a personal email address",
        }[self.relationship]


# --- the live thread -------------------------------------------------------------------------
@dataclass(frozen=True)
class ThreadMessage:
    sender: str  # a token: ⟦PERSON_….full⟧, ⟦EMAIL_…⟧ or ⟦ME.full⟧
    from_me: bool
    sent_at: datetime
    text: str  # L1


@dataclass
class LiveContext:
    mode: Mode
    conversation_id: str | None
    audience: Audience
    thread: list[ThreadMessage]
    subject: str | None  # L1
    instruction: str | None  # L1
    tokens: dict[str, str]  # token → display value: this request only, never stored
    thread_people: list[Address]
    decision: Decision
    one_off: bool
    me: Recipient
    suspicious: bool = False
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def received(self) -> list[str]:
        return [m.text for m in self.thread if not m.from_me]

    @property
    def last_received(self) -> str | None:
        texts = self.received
        return texts[-1] if texts else None

    @property
    def grounding(self) -> str:
        """Everything the draft may rely on (L1): the thread, the subject and the instruction."""
        return "\n".join([m.text for m in self.thread] + [self.subject or "", self.instruction or ""])


def _in(domain: str, domains: frozenset[str]) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in domains)


def _url_safe(conversation_id: str) -> str:
    return conversation_id.replace("+", "-").replace("/", "_")


def refusal(decision: Decision) -> DraftError:
    """Why an excluded conversation is refused, without content. Someone who can't be checked (no
    address) is neither the user's rule nor the organisation's: it's refused, never one-off."""
    kinds = sorted({r.kind for r in decision.reasons})
    if decision.by_tenant:
        unverifiable = {"unknown_participant", "members_unknown"}
        tenant = {r.kind for r in decision.reasons if r.scope == "tenant"}
        by = "unverifiable" if tenant <= unverifiable else "organisation"
        return DraftError("conversation_excluded", 403, by=by, reasons=kinds)
    return DraftError("conversation_excluded", 409, by="you", reasons=kinds, oneOffAllowed=True)


async def _thread_headers(source: WorkspaceSource, conversation_id: str) -> list[MessageHeader]:
    headers = [h for h in await source.thread_headers(conversation_id) if not h.is_draft]
    if not headers and _url_safe(conversation_id) != conversation_id:
        # Outlook's add-in API may give the conversation ID in standard base64 where Graph uses the
        # URL-safe alphabet (to verify in the add-in spike); try that form too.
        headers = [h for h in await source.thread_headers(_url_safe(conversation_id)) if not h.is_draft]
    return sorted(headers, key=lambda h: h.sent_at)


def _default_recipients(
    headers: Sequence[MessageHeader], me: str, reply_all: bool
) -> tuple[list[Address], list[Address]]:
    """Who a reply goes to when the client didn't say (the web test bench): the sender of the last
    message from someone else; with reply-all, everyone else on it too."""
    last = next((h for h in reversed(headers) if h.sender.email.lower() != me), headers[-1])
    if last.sender.email.lower() == me:  # following up on your own message: the same people
        return list(last.to), (list(last.cc) if reply_all else [])
    to = [last.sender]
    cc = (
        [a for a in (*last.to, *last.cc) if a.email.lower() not in (me, last.sender.email.lower())] if reply_all else []
    )
    return to, cc


def _dedupe(addresses: Sequence[Address], me: str, skip: set[str] | None = None) -> list[Address]:
    seen = set(skip or ())
    out = []
    for a in addresses:
        e = a.email.strip().lower()
        if not e or e == me or e in seen:
            continue
        seen.add(e)
        out.append(Address(email=e, name=(a.name or "").strip() or None))
    return out


def _named(addresses: list[Address], known: dict[str, str]) -> list[Address]:
    """Fill in missing or address-like display names from the thread and the directory."""
    out = []
    for a in addresses:
        name = a.name if a.name and "@" not in a.name else known.get(a.email)
        out.append(Address(email=a.email, name=name))
    return out


async def gather(
    source: WorkspaceSource,
    *,
    ex_engine: ExclusionEngine,
    matcher: Matcher,
    hasher: Hasher,
    directory: Directory,
    self_email: str,
    mode: Mode,
    conversation_id: str | None,
    to: Sequence[Address] | None,
    cc: Sequence[Address] | None,
    subject: str | None,
    instruction: str | None,
    reply_all: bool = False,
    one_off: bool = False,
    known_people: Sequence[Person] = (),
) -> LiveContext:
    """`known_people`: names and addresses from the user's Sources index, so names mentioned in the
    thread or the instruction are tokenised as the learner would (same gazetteer reach)."""
    me = self_email.lower()
    headers: list[MessageHeader] = []
    if mode == "reply":
        if not conversation_id:
            raise DraftError("conversation_required", 422)
        headers = await _thread_headers(source, conversation_id)
        if not headers:
            raise DraftError("thread_not_found", 404)
        # From here on, Graph's own form of the ID: rules, hashes and lookups all match it.
        conversation_id = headers[0].conversation_id
    if to is None and cc is None and headers:
        to, cc = _default_recipients(headers, me, reply_all)
    to_list = _dedupe(list(to or []), me)
    cc_list = _dedupe(list(cc or []), me, {a.email for a in to_list})
    if not to_list and not cc_list:
        raise DraftError("recipients_required", 422)
    if len(to_list) + len(cc_list) > MAX_RECIPIENTS:
        raise DraftError("too_many_recipients", 422)

    thread_people = [a for h in headers for a in h.participants]
    known = {a.email.lower(): a.name for a in thread_people if a.email and a.name}
    known |= {p.email: p.full_name for p in directory.people if p.email}
    to_list, cc_list = _named(to_list, known), _named(cc_list, known)

    # 1-2. Decide from metadata before any text is read.
    decision = ex_engine.conversation(
        conversation_id if mode == "reply" else None, [*thread_people, *to_list, *cc_list]
    )
    if decision.excluded and (decision.by_tenant or not one_off):
        raise refusal(decision)

    g = Gazetteer(me=directory.me)
    for p in directory.people:
        g.add(p.full_name, p.email)
    for a in [*thread_people, *to_list, *cc_list]:
        g.add(a.name, a.email)
    for person in known_people:
        g.add(person.full_name, person.email)
    redactor = Redactor(matcher, g, hasher)
    tokens: dict[str, str] = {}
    counts: dict[str, int] = {}
    suspicious = False

    def red(text: str | None, what: str, *, hidden: bool = False) -> Redacted | None:
        nonlocal suspicious
        if not text or not text.strip():
            return None
        try:
            r = redactor.redact(text[:MAX_MESSAGE_CHARS], hidden_seen=hidden)
        except RedactionBlocked as e:
            raise DraftError(f"{what}_blocked", 422, reason=e.reason) from None
        tokens.update({t: v for t, (_, v) in r.tokens.items()})
        for k, n in r.counts.items():
            counts[k] = counts.get(k, 0) + n
        suspicious = suspicious or r.suspicious
        return r

    def recipient(a: Address) -> Recipient:
        forms = redactor.person_forms(Person(a.name, a.email)) if a.name else {}
        tokens.update({tok: name for tok, name in forms.values()})
        if forms:
            return Recipient(a, forms, forms["full"][0])
        tok = redactor.email_token(a.email)
        tokens[tok] = a.email
        return Recipient(a, forms, tok)

    def sender_token(a: Address) -> str:
        if a.email.lower() == me:
            return "⟦ME.full⟧"
        if a.name:
            tok, name = redactor.person_forms(Person(a.name, a.email.lower()))["full"]
            tokens[tok] = name
            return tok
        if a.email:
            tok = redactor.email_token(a.email)
            tokens[tok] = a.email.lower()
            return tok
        return "someone"

    me_forms = redactor.person_forms(directory.me, me=True)
    tokens.update({tok: name for tok, name in me_forms.values()})

    # 3. Two-phase fetch: the last few messages' own words, only now.
    recent = headers[-MAX_THREAD_MESSAGES:]
    contents = await asyncio.gather(*(source.message(h.id) for h in recent))
    thread: list[ThreadMessage] = []
    thread_subject: str | None = None
    for h, m in zip(recent, contents, strict=True):
        if m is None:
            continue
        own, _quoted = strip_quotes(m.body) if not m.quoted else (m.body, m.quoted)
        r = red(strip_signature_noise(own), "thread", hidden=m.hidden)
        thread_subject = m.subject or thread_subject
        if r is None:
            continue
        thread.append(ThreadMessage(sender_token(h.sender), h.sender.email.lower() == me, h.sent_at, r.text))
    if mode == "reply" and not thread:
        raise DraftError("thread_empty", 404)

    subj = red(subject or thread_subject, "subject")
    instr = red(instruction, "instruction")
    audience_people = [*to_list, *cc_list]
    audience = Audience(
        relationship=labels.relationship(
            audience_people,
            manager=directory.manager,
            reports=directory.reports,
            org_domains=directory.org_domains,
        ),
        to=[recipient(a) for a in to_list],
        cc=[recipient(a) for a in cc_list],
        internal=sum(1 for a in audience_people if _in(a.domain, directory.org_domains)),
        external=sum(1 for a in audience_people if not _in(a.domain, directory.org_domains)),
    )
    return LiveContext(
        mode=mode,
        conversation_id=conversation_id if mode == "reply" else None,
        audience=audience,
        thread=thread,
        subject=subj.text if subj else None,
        instruction=instr.text if instr else None,
        tokens=tokens,
        thread_people=thread_people,
        decision=decision,
        one_off=one_off and decision.excluded,
        me=Recipient(Address(me, directory.me.full_name), me_forms, "⟦ME.full⟧"),
        suspicious=suspicious,
        counts=counts,
    )
