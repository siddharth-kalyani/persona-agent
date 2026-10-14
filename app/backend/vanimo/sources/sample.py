"""The sample workspace: a synthetic Microsoft 365 tenant for building and demoing Vanimo
while Entra/Graph access is pending.

"Kestrel Analytics" is a fictional IT-services firm (our beachhead customer shape) with
India and US staff, three clients, a vendor, and the hard cases the data controls must
handle: client codenames, a 60-person group chat, a hidden chat, an unnamed group chat,
a meeting chat, forwards, Hinglish subjects, personal (consumer) mail, a private calendar
event and a recurring series. All people, companies and domains are invented; domains use
the reserved `.example` TLD (RFC 2606), and consumer-mail addresses are fictional.

The data is deterministic (fixed seed, stable IDs); timestamps are relative to "now" so
the workspace always looks recent.
"""

from __future__ import annotations

import random
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from vanimo.sources.base import (
    Address,
    Chat,
    ChatMessage,
    Event,
    MessageContent,
    MessageHeader,
    Profile,
    SentHeader,
)
from vanimo.sources.sample_content import AGENDAS, CHAT_SCRIPTS, ME, THREAD_SCRIPTS

ORG_DOMAIN = "kestrel.example"
SAMPLE_SEED = 20261013


def _p(name: str, domain: str = ORG_DOMAIN, local: str | None = None) -> Address:
    local = local or name.lower().replace(" ", ".")
    return Address(email=f"{local}@{domain}", name=name)


# --- People -------------------------------------------------------------------------------
MANAGER = _p("Meera Iyer")
REPORTS = [_p("Rahul Verma"), _p("Ana Fernandes")]
PEERS = [_p("Vikram Shah"), _p("Priya Nair"), _p("Arjun Mehta"), _p("Sarah Collins"), _p("Neha Kulkarni")]
EXEC = _p("David Brooks")
ACME = [_p("John Miller", "acmeretail.example"), _p("Lisa Chen", "acmeretail.example")]
BLUEFIN = [_p("Karan Malhotra", "bluefinbank.example"), _p("Deepa Rao", "cards.bluefinbank.example")]
ORION = [_p("Emily Park", "orionhealth.example")]
VENDOR = [_p("Tom Becker", "cloudnest.example")]
FAMILY = Address(email="nisha.home.1987@gmail.com", name="Nisha (home)")
EVERYONE_INTERNAL = [MANAGER, *REPORTS, *PEERS, EXEC]

PROFILES = {
    MANAGER.email: Profile("Meera Iyer", MANAGER.email, "Director, Delivery", "Delivery"),
}


@dataclass(frozen=True)
class _Thread:
    subject: str
    to: tuple[Address, ...]
    cc: tuple[Address, ...] = ()
    messages: int = 1


THREADS: list[_Thread] = [
    _Thread("Weekly status: Acme replatforming", (ACME[0],), (MANAGER,), 4),
    _Thread("Re: Acme UAT sign-off", (ACME[1],), (ACME[0], REPORTS[0]), 3),
    _Thread("Acme invoice for September", (ACME[0],), (PEERS[3],), 1),
    _Thread("Project Falcon timeline", (BLUEFIN[0],), (MANAGER, PEERS[0]), 5),
    _Thread("Re: Falcon data migration risks", (BLUEFIN[1], BLUEFIN[0]), (), 3),
    _Thread("FW: Bluefin SOW v3 (Project Falcon)", (MANAGER,), (), 1),
    _Thread("Bluefin steering committee pack", (BLUEFIN[0], EXEC), (MANAGER,), 2),
    _Thread("Orion Health discovery workshop", (ORION[0],), (PEERS[1],), 2),
    _Thread("Re: Orion PHI handling questions", (ORION[0],), (), 2),
    _Thread("Please prepare the UAT checklist", (REPORTS[0],), (REPORTS[1],), 1),
    _Thread("Re: Leave plan for Diwali week", (MANAGER,), (), 2),
    _Thread("Kal ka standup thoda late karte hain", (REPORTS[0], REPORTS[1]), (), 1),
    _Thread("Re: Appraisal inputs for Rahul", (MANAGER,), (), 2),
    _Thread("Hiring: senior data engineer shortlist", (PEERS[2],), (MANAGER,), 3),
    _Thread("Re: Q3 delivery review deck", (EXEC,), (MANAGER, PEERS[0]), 2),
    _Thread("CloudNest renewal quote", (VENDOR[0],), (PEERS[3],), 2),
    _Thread("Fwd: CloudNest outage RCA", (PEERS[0], PEERS[2]), (), 1),
    _Thread("Re: Knowledge-transfer plan for Ana", (REPORTS[1],), (MANAGER,), 2),
    _Thread("Team lunch on Friday?", (*REPORTS, PEERS[1], PEERS[4]), (), 1),
    _Thread("Re: Weekend plans", (FAMILY,), (), 2),
    _Thread("Operation Monsoon: pricing approach", (EXEC, MANAGER), (), 2),
    _Thread("Re: Travel to Pune next week", (PEERS[4],), (), 1),
    _Thread("Re: Security questionnaire for Bluefin", (BLUEFIN[1],), (PEERS[2],), 2),
    _Thread("Sprint 14 retro notes", (*REPORTS, PEERS[2]), (), 1),
]

LARGE_GROUP = tuple(
    [MANAGER, *REPORTS, *PEERS, EXEC]
    + [_p(f"Kestrel Colleague {i:02d}", local=f"colleague{i:02d}") for i in range(1, 52)]
)


def _chats(self_addr: Address, now: datetime) -> list[Chat]:
    def ago(hours: float) -> datetime:
        return now - timedelta(hours=hours)

    def with_self(*members: Address) -> tuple[Address, ...]:
        return (self_addr, *members)

    return [
        Chat("smp-chat-001", "oneOnOne", None, with_self(MANAGER), ago(2)),
        Chat("smp-chat-002", "oneOnOne", None, with_self(REPORTS[0]), ago(5)),
        Chat("smp-chat-003", "oneOnOne", None, with_self(REPORTS[1]), ago(30)),
        Chat("smp-chat-004", "oneOnOne", None, with_self(PEERS[0]), ago(8)),
        Chat("smp-chat-005", "oneOnOne", None, with_self(PEERS[1]), ago(50)),
        Chat("smp-chat-006", "oneOnOne", None, with_self(BLUEFIN[0]), ago(20)),  # external (federated)
        Chat(
            "smp-chat-007",
            "group",
            "Delivery leads",
            with_self(MANAGER, PEERS[0], PEERS[1], PEERS[2], PEERS[4]),
            ago(3),
        ),
        Chat("smp-chat-008", "group", "Falcon war room", with_self(PEERS[0], REPORTS[0], *BLUEFIN), ago(1)),
        Chat("smp-chat-009", "group", "All Kestrel India", with_self(*LARGE_GROUP), ago(6)),
        Chat("smp-chat-010", "group", None, with_self(REPORTS[0], PEERS[1], REPORTS[1]), ago(70)),  # unnamed
        Chat("smp-chat-011", "group", "Old Acme pilot", with_self(ACME[0], PEERS[3]), ago(24 * 90), hidden=True),
        Chat(
            "smp-chat-012",
            "meeting",
            "Acme weekly sync",
            with_self(*ACME, MANAGER),
            ago(26),
            join_url="https://teams.example/l/meetup-join/acme-06",  # the series' latest past occurrence
        ),
        Chat("smp-chat-013", "group", "Monsoon pricing (confidential)", with_self(EXEC, MANAGER), ago(40)),
    ]


def _events(self_addr: Address, now: datetime) -> list[Event]:
    base = (now - timedelta(days=now.weekday())).replace(hour=10, minute=0, second=0, microsecond=0)
    events: list[Event] = []
    # Recurring: Acme weekly sync (organised by you), six occurrences back, two ahead.
    for i in range(-6, 3):
        start = base + timedelta(weeks=i, days=1)
        events.append(
            Event(
                id=f"smp-evt-acme-{i + 6:02d}",
                subject="Acme weekly sync",
                start=start,
                end=start + timedelta(hours=1),
                organizer=self_addr,
                attendees=(*ACME, MANAGER),
                series_id="smp-series-acme",
                is_online=True,
                is_organizer=True,
                join_url=f"https://teams.example/l/meetup-join/acme-{i + 6:02d}",
            )
        )
    # Recurring 1:1 with the manager (organised by her).
    for i in range(-4, 2):
        start = base + timedelta(weeks=i, days=3, hours=5)
        events.append(
            Event(
                id=f"smp-evt-1on1-{i + 4:02d}",
                subject="Meera / you 1:1",
                start=start,
                end=start + timedelta(minutes=30),
                organizer=MANAGER,
                attendees=(self_addr,),
                series_id="smp-series-1on1",
                is_online=True,
                join_url=f"https://teams.example/l/meetup-join/1on1-{i + 4:02d}",
            )
        )
    singles = [
        ("smp-evt-falcon-sc", "Falcon steering committee", -9, BLUEFIN[0], (*BLUEFIN, EXEC, MANAGER), True, False),
        ("smp-evt-orion", "Orion Health discovery workshop", -16, self_addr, (ORION[0], PEERS[1]), True, False),
        ("smp-evt-allhands", "Kestrel all hands", -3, EXEC, tuple(LARGE_GROUP[:40]), True, False),
        ("smp-evt-doctor", "Doctor appointment", -2, self_addr, (), False, True),
        ("smp-evt-monsoon", "Operation Monsoon pricing review", 2, EXEC, (MANAGER, self_addr), True, False),
    ]
    for eid, subject, day, organizer, attendees, online, private in singles:
        start = base + timedelta(days=day, hours=4)
        events.append(
            Event(
                id=eid,
                subject=subject,
                start=start,
                end=start + timedelta(hours=1),
                organizer=organizer,
                attendees=attendees,
                is_online=online,
                is_private=private,
                is_organizer=organizer == self_addr,
                join_url=f"https://teams.example/l/meetup-join/{eid}" if online else None,
            )
        )
    return events


def _conversation(self_addr: Address, now: datetime) -> list[MessageContent]:
    """Every email in the sample mailbox (sent and received), oldest first per thread.

    Sent messages keep the IDs smp-msg-0001… in thread order, as the header pass has always seen
    them; replies from others are smp-in-0001….
    """
    rng = random.Random(SAMPLE_SEED)  # noqa: S311 - deterministic sample data, not security
    first = (self_addr.name or "You").split()[0]
    out: list[MessageContent] = []
    n_sent = n_in = 0
    for t_index, thread in enumerate(THREADS):
        conversation = f"smp-conv-{t_index + 1:03d}"
        start_days = rng.uniform(2, 110)
        script = THREAD_SCRIPTS[thread.subject]
        history: list[MessageContent] = []
        for m, (who, text) in enumerate(script):
            prefix = "" if m == 0 or thread.subject.lower().startswith(("re:", "fw:", "fwd:")) else "Re: "
            when = now - timedelta(days=start_days - m * rng.uniform(0.2, 2.0), minutes=rng.randint(0, 600))
            body = text.format(first=first, full=self_addr.name or first)
            quoted = "\n\n".join(f"From: {h.sender.name}\n{h.body}" for h in reversed(history[-3:]))
            if who == ME:
                n_sent += 1
                msg = MessageContent(
                    id=f"smp-msg-{n_sent:04d}", conversation_id=conversation, subject=prefix + thread.subject,
                    sent_at=when, sender=self_addr, to=thread.to, cc=thread.cc, direction="sent", body=body,
                    quoted=quoted,
                )  # fmt: skip
            else:
                n_in += 1
                them = thread.to[0]
                msg = MessageContent(
                    id=f"smp-in-{n_in:04d}", conversation_id=conversation,
                    subject="Re: " + thread.subject.removeprefix("Re: "),
                    sent_at=when, sender=them, to=(self_addr,), cc=(), direction="received", body=body, quoted=quoted,
                )  # fmt: skip
            history.append(msg)
            out.append(msg)
    return out


def _sent(self_addr: Address, now: datetime) -> list[SentHeader]:
    sent = [
        SentHeader(id=m.id, conversation_id=m.conversation_id, subject=m.subject, sent_at=m.sent_at, to=m.to, cc=m.cc)
        for m in _conversation(self_addr, now)
        if m.direction == "sent"
    ]
    sent.sort(key=lambda h: h.sent_at, reverse=True)
    return sent


def _chat_messages(self_addr: Address, now: datetime, chat: Chat) -> list[ChatMessage]:
    first = (self_addr.name or "You").split()[0]
    by_name = {m.name: m for m in chat.members}
    script = CHAT_SCRIPTS.get(chat.id, [])
    last = chat.last_activity_at or now
    out = []
    for i, (who, text) in enumerate(script):
        sender = self_addr if who == ME else by_name.get(who, Address(email="unknown@kestrel.example", name=who))
        out.append(
            ChatMessage(
                id=f"{chat.id}-m{i + 1:02d}", chat_id=chat.id, sender=sender,
                created_at=last - timedelta(minutes=7 * (len(script) - i - 1)),
                text=text.format(first=first), from_me=who == ME,
            )
        )  # fmt: skip
    return out


def _self_address(email: str | None) -> Address:
    """The signed-in person as they appear in the sample workspace (on the fictional domain)."""
    local = (email or "you").split("@", 1)[0].lower()
    name = " ".join(part.capitalize() for part in local.replace("_", ".").split(".") if part) or "You"
    return Address(email=f"{local}@{ORG_DOMAIN}", name=name)


class SampleSource:
    kind = "sample"

    def __init__(self, email: str | None, now: datetime | None = None) -> None:
        self.me = _self_address(email)
        self._now = (now or datetime.now(UTC)).replace(second=0, microsecond=0)

    async def profile(self) -> Profile:
        return Profile(self.me.name, self.me.email, "Engagement Manager", "Delivery")

    async def manager(self) -> Profile | None:
        return PROFILES[MANAGER.email]

    async def recent_sent(self, top: int = 5) -> list[SentHeader]:
        return _sent(self.me, self._now)[:top]

    async def sent_headers(self) -> AsyncIterator[SentHeader]:
        for header in _sent(self.me, self._now):
            yield header

    async def chats(self) -> AsyncIterator[Chat]:
        for chat in _chats(self.me, self._now):
            yield chat

    async def events(self, start: datetime, end: datetime) -> AsyncIterator[Event]:
        for event in _events(self.me, self._now):
            if start <= event.start <= end:
                yield event

    async def org_domains(self) -> frozenset[str]:
        return frozenset({ORG_DOMAIN})

    async def direct_reports(self) -> list[Address]:
        return list(REPORTS)

    # --- content (callers must pass the onboarding gate) ----------------------------------
    async def thread_headers(self, conversation_id: str) -> list[MessageHeader]:
        return [
            MessageHeader(m.id, m.conversation_id, m.sent_at, m.sender, m.to, m.cc, m.direction)
            for m in _conversation(self.me, self._now)
            if m.conversation_id == conversation_id
        ]

    async def message(self, message_id: str) -> MessageContent | None:
        return next((m for m in _conversation(self.me, self._now) if m.id == message_id), None)

    async def all_messages(self) -> list[MessageContent]:
        """Sample-only convenience for the Sample workspace screen."""
        return _conversation(self.me, self._now)

    async def chat_messages(self, chat_id: str) -> AsyncIterator[ChatMessage]:
        chat = next((c for c in _chats(self.me, self._now) if c.id == chat_id), None)
        if chat:
            for m in _chat_messages(self.me, self._now, chat):
                yield m

    async def event_agenda(self, event_id: str) -> str | None:
        event = next((e for e in _events(self.me, self._now) if e.id == event_id), None)
        return AGENDAS.get(event.subject or "") if event else None
