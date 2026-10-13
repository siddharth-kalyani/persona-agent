"""Read the user's Sources index (decrypted for its owner only) and decide, row by row, whether
each source is excluded and why. Used by the review screen and My data controls."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from vanimo.controls.engine import ExclusionEngine, Reason
from vanimo.controls.neversend import render_removed
from vanimo.db.session import UserRef
from vanimo.sources.base import Address
from vanimo.vault import Vault

LARGE_CHAT = 25  # group chats this big are suggested for review when excluding a person


@dataclass
class Person:
    id: uuid.UUID
    key_hash: str
    domain_hash: str
    email: str
    name: str | None
    domain: str
    internal: bool
    consumer: bool
    sent: int
    chats: int
    meetings: int
    last: datetime | None

    @property
    def label(self) -> str:
        return render_removed(self.name) or self.email


@dataclass
class Thread:
    id: uuid.UUID
    key_hash: str
    subject: str | None
    count: int
    last: datetime | None
    forward: bool
    people: set[uuid.UUID] = field(default_factory=set)


@dataclass
class ChatRow:
    id: uuid.UUID
    key_hash: str
    chat_type: str
    label: str
    members: int
    hidden: bool
    last: datetime | None
    people: set[uuid.UUID] = field(default_factory=set)


@dataclass
class Meeting:
    id: uuid.UUID
    key_hash: str
    series_hash: str | None
    subject: str | None
    start: datetime
    private: bool
    online: bool
    organizer: bool
    people: set[uuid.UUID] = field(default_factory=set)


@dataclass
class IndexView:
    people: dict[uuid.UUID, Person]
    threads: dict[uuid.UUID, Thread]
    chats: dict[uuid.UUID, ChatRow]
    meetings: dict[uuid.UUID, Meeting]

    def by_hash(self) -> dict[tuple[str, str], str]:
        """(kind, key hash) → display label, to show what each rule excludes."""
        out: dict[tuple[str, str], str] = {}
        for p in self.people.values():
            out[("person", p.key_hash)] = p.label
            out[("domain", p.domain_hash)] = p.domain
        for t in self.threads.values():
            out[("thread", t.key_hash)] = render_removed(t.subject) or "(no subject)"
        for c in self.chats.values():
            out[("chat", c.key_hash)] = c.label
        for m in self.meetings.values():
            out[("meeting", m.key_hash)] = render_removed(m.subject) or "(no subject)"
            if m.series_hash:
                out[("series", m.series_hash)] = (render_removed(m.subject) or "(no subject)") + " (series)"
        return out


async def load_index(conn: AsyncConnection, vault: Vault, ref: UserRef) -> IndexView:
    def dec(value: str | None, purpose: str) -> str | None:
        return vault.decrypt_user(ref.tenant_id, ref.user_id, value, purpose)

    people = {
        r.id: Person(
            r.id, r.key_hash, r.domain_hash, dec(r.email_enc, "email") or "", dec(r.name_enc, "name"),
            dec(r.domain_enc, "domain") or "", r.is_internal, r.is_consumer, r.sent_count, r.chat_count,
            r.meeting_count, r.last_contact_at,
        )
        for r in (await conn.execute(text("select * from vanimo.source_people"))).all()
    }  # fmt: skip
    threads = {
        r.id: Thread(r.id, r.key_hash, dec(r.subject_enc, "subject"), r.message_count, r.last_sent_at, r.is_forward)
        for r in (await conn.execute(text("select * from vanimo.source_threads"))).all()
    }
    for r in (
        await conn.execute(
            text(
                "select distinct m.thread_id, mp.person_id from vanimo.source_messages m "
                "join vanimo.source_message_people mp on mp.message_id = m.id"
            )
        )
    ).all():
        threads[r.thread_id].people.add(r.person_id)
    chats = {
        r.id: ChatRow(
            r.id, r.key_hash, r.chat_type, render_removed(dec(r.label_enc, "chat_label")) or "(chat)",
            r.member_count, r.hidden, r.last_activity_at,
        )
        for r in (await conn.execute(text("select * from vanimo.source_chats"))).all()
    }  # fmt: skip
    for r in (await conn.execute(text("select chat_id, person_id from vanimo.source_chat_people"))).all():
        chats[r.chat_id].people.add(r.person_id)
    meetings = {
        r.id: Meeting(
            r.id, r.key_hash, r.series_hash, dec(r.subject_enc, "subject"), r.start_at, r.is_private, r.is_online,
            r.is_organizer,
        )
        for r in (await conn.execute(text("select * from vanimo.source_meetings"))).all()
    }  # fmt: skip
    for r in (await conn.execute(text("select meeting_id, person_id from vanimo.source_meeting_people"))).all():
        meetings[r.meeting_id].people.add(r.person_id)
    return IndexView(people, threads, chats, meetings)


# --- Decisions ------------------------------------------------------------------------------


@dataclass
class Status:
    excluded: bool
    direct_rule_id: str | None  # a rule on this very item, which the user can remove here
    via: list[str]  # human-readable reasons ("Rahul Verma", "Your organisation: Bluefin Bank")
    locked: bool  # excluded by the organisation: users can't lift it


class Evaluator:
    def __init__(self, view: IndexView, engine: ExclusionEngine, account_names: dict[str, str]) -> None:
        self.view = view
        self.engine = engine
        self.account_names = account_names
        self.labels = view.by_hash()
        self.rule_labels = {r.id: self.labels.get((r.kind, r.key_hash), r.kind) for r in engine.user_rules}

    def _describe(self, reasons: list[Reason], direct_kind: str | None) -> Status:
        via: list[str] = []
        direct: str | None = None
        for r in reasons:
            if r.scope == "tenant":
                via.append(
                    f"Your organisation: {self.account_names.get(r.account_id or '', 'client account')}"
                    if r.kind == "client_account"
                    else "Your organisation: only approved clients"
                )
            elif r.kind == direct_kind and direct is None:
                direct = r.rule_id
            else:
                via.append(self.rule_labels.get(r.rule_id or "", r.kind))
        return Status(bool(reasons), direct, list(dict.fromkeys(via)), any(r.scope == "tenant" for r in reasons))

    def _people_reasons(self, ids: set[uuid.UUID], chat_hash: str | None = None) -> list[Reason]:
        out: list[Reason] = []
        for pid in ids:
            p = self.view.people.get(pid)
            if p:
                out += self.engine.person_reasons(Address(p.email, p.name), chat_hash=chat_hash)
        return out

    def person(self, p: Person) -> Status:
        return self._describe(self.engine.person_reasons(Address(p.email, p.name)), "person")

    def domain(self, domain: str, domain_hash: str) -> Status:
        reasons = self.engine.domain_reasons(domain)
        # Show the user's own rule on exactly this domain as the direct one.
        return self._describe(reasons, "domain")

    def thread(self, t: Thread) -> Status:
        reasons: list[Reason] = []
        if rule := self.engine.rule("thread", t.key_hash):
            reasons.append(Reason("user", "thread", rule.id))
        return self._describe(reasons + self._people_reasons(t.people), "thread")

    def chat(self, c: ChatRow) -> Status:
        reasons: list[Reason] = []
        if rule := self.engine.rule("chat", c.key_hash):
            reasons.append(Reason("user", "chat", rule.id))
        return self._describe(reasons + self._people_reasons(c.people, chat_hash=c.key_hash), "chat")

    def meeting(self, m: Meeting, *, as_series: bool = False) -> Status:
        reasons: list[Reason] = []
        if rule := self.engine.rule("meeting", m.key_hash):
            reasons.append(Reason("user", "meeting", rule.id))
        if rule := self.engine.rule("series", m.series_hash):
            reasons.append(Reason("user", "series", rule.id))
        return self._describe(reasons + self._people_reasons(m.people), "series" if as_series else "meeting")


# --- Impact preview ---------------------------------------------------------------------------


def impact(view: IndexView, kind: str, item_id: uuid.UUID, message_people: dict[uuid.UUID, set[uuid.UUID]],
           thread_messages: dict[uuid.UUID, int]) -> dict[str, Any]:  # fmt: skip
    """What a rule on this item would remove: "214 emails in 37 threads, 1 chat, 3 meetings".

    `message_people`: person id → message ids; `thread_messages`: thread id → message count."""
    people: set[uuid.UUID] = set()
    threads: set[uuid.UUID] = set()
    chats: set[uuid.UUID] = set()
    meetings: set[uuid.UUID] = set()
    emails: set[uuid.UUID] = set()
    if kind in ("person", "domain"):
        if kind == "person":
            people = {item_id}
        else:
            anchor = view.people[item_id]
            people = {p.id for p in view.people.values() if p.domain_hash == anchor.domain_hash}
        for pid in people:
            emails |= message_people.get(pid, set())
        threads = {t.id for t in view.threads.values() if t.people & people}
        chats = {c.id for c in view.chats.values() if c.people & people}
        meetings = {m.id for m in view.meetings.values() if m.people & people}
        email_count = len(emails)
    elif kind == "thread":
        threads = {item_id}
        email_count = thread_messages.get(item_id, 0)
    elif kind == "chat":
        chats = {item_id}
        email_count = 0
    elif kind == "meeting":
        meetings = {item_id}
        email_count = 0
    elif kind == "series":
        series = view.meetings[item_id].series_hash
        meetings = {m.id for m in view.meetings.values() if m.series_hash == series}
        email_count = 0
    else:
        raise ValueError(kind)
    chat_list = sorted(
        (
            {
                "id": str(c.id),
                "label": c.label,
                "members": c.members,
                "large": c.members >= LARGE_CHAT,
            }
            for c in (view.chats[i] for i in chats)
        ),
        key=lambda c: (-int(c["large"]), c["label"]),
    )
    return {
        "emails": email_count,
        "threads": len(threads),
        "chats": len(chats),
        "meetings": len(meetings),
        "chatList": chat_list if kind in ("person", "domain") else [],
    }


async def message_links(conn: AsyncConnection) -> tuple[dict[uuid.UUID, set[uuid.UUID]], dict[uuid.UUID, int]]:
    by_person: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for r in (await conn.execute(text("select message_id, person_id from vanimo.source_message_people"))).all():
        by_person[r.person_id].add(r.message_id)
    counts = {
        r.thread_id: r.n
        for r in (
            await conn.execute(text("select thread_id, count(*) as n from vanimo.source_messages group by thread_id"))
        ).all()
    }
    return by_person, counts
