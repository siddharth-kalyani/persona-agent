"""The header pass (architecture §6.5, onboarding step 2): build the user's Sources index from
metadata only — sent-mail headers, chat rosters and the calendar. No message text is read.

Never-send words are applied to subjects, topics and display names *before* anything is
stored, and every display field is then vault-encrypted. The index is rebuilt in full on each
scan (one transaction), so it never holds a mix of old and new rows.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from vanimo.controls.neversend import Matcher
from vanimo.controls.store import hasher_for, load_matcher, lock_user_controls
from vanimo.db.session import UserRef, user_tx
from vanimo.logs import get_logger
from vanimo.sources.base import CONSUMER_DOMAINS, Address, WorkspaceSource
from vanimo.vault import Vault

log = get_logger("vanimo.scan")

CALENDAR_BACK = timedelta(days=365)
CALENDAR_AHEAD = timedelta(days=90)
FORWARD_PREFIXES = ("fw:", "fwd:")


@dataclass
class _Person:
    email: str
    name: str | None = None
    sent: int = 0
    chats: int = 0
    meetings: int = 0
    last: datetime | None = None

    def touch(self, name: str | None, when: datetime | None) -> None:
        self.name = self.name or name
        if when and (self.last is None or when > self.last):
            self.last = when


@dataclass
class _Index:
    people: dict[str, _Person] = field(default_factory=dict)
    threads: dict[str, dict[str, Any]] = field(default_factory=dict)
    messages: list[dict[str, Any]] = field(default_factory=list)
    chats: list[dict[str, Any]] = field(default_factory=list)
    meetings: list[dict[str, Any]] = field(default_factory=list)

    def person(self, addr: Address, when: datetime | None) -> _Person:
        p = self.people.setdefault(addr.email.lower(), _Person(addr.email.lower()))
        p.touch(addr.name, when)
        return p


def chat_label(topic: str | None, member_names: list[str]) -> str:
    """Teams-style label: the topic, or up to three member names and "+N"."""
    if topic:
        return topic
    shown = ", ".join(member_names[:3])
    return f"{shown} +{len(member_names) - 3}" if len(member_names) > 3 else shown or "(chat)"


async def _collect(source: WorkspaceSource, self_email: str, now: datetime) -> _Index:
    idx = _Index()
    me = self_email.lower()
    seen_messages: set[str] = set()
    async for h in source.sent_headers():
        # Delta paging can return the same message twice; count it once.
        if h.id in seen_messages:
            continue
        seen_messages.add(h.id)
        thread = idx.threads.setdefault(
            h.conversation_id, {"subject": h.subject, "count": 0, "last": None, "forward": False}
        )
        thread["count"] += 1
        if thread["last"] is None or h.sent_at > thread["last"]:
            thread["last"], thread["subject"] = h.sent_at, h.subject
        if (h.subject or "").strip().lower().startswith(FORWARD_PREFIXES):
            thread["forward"] = True
        people = []
        for addr in {a.email.lower(): a for a in h.participants}.values():  # once per message
            if addr.email.lower() == me:
                continue
            p = idx.person(addr, h.sent_at)
            p.sent += 1
            people.append(p.email)
        idx.messages.append({"id": h.id, "conv": h.conversation_id, "sent_at": h.sent_at, "people": people})
    chats_by_id: dict[str, Any] = {}
    async for c in source.chats():
        chats_by_id[c.id] = c  # a chat that moves while pages are read can appear twice: last wins
    for c in chats_by_id.values():
        members = list({m.email.lower(): m for m in c.members if m.email.lower() != me}.values())
        for m in members:
            idx.person(m, c.last_activity_at).chats += 1
        idx.chats.append(
            {
                "id": c.id,
                "type": c.chat_type,
                "topic": c.topic,
                "label": chat_label(c.topic, [m.name or m.email for m in members]),
                "members": [m.email.lower() for m in members],
                "hidden": c.hidden,
                "last": c.last_activity_at,
            }
        )
    events_by_id: dict[str, Any] = {}
    async for e in source.events(now - CALENDAR_BACK, now + CALENDAR_AHEAD):
        events_by_id[e.id] = e
    for e in events_by_id.values():
        attendees = [a for a in (*e.attendees, *([e.organizer] if e.organizer else [])) if a.email.lower() != me]
        unique = list({a.email.lower(): a for a in attendees}.values())
        for a in unique:
            idx.person(a, e.start).meetings += 1
        idx.meetings.append(
            {
                "id": e.id,
                "series": e.series_id,
                "subject": e.subject,
                "start": e.start,
                "private": e.is_private,
                "online": e.is_online,
                "organizer": e.is_organizer,
                "people": [a.email.lower() for a in unique],
            }
        )
    return idx


def _is_internal(domain: str, org_domains: frozenset[str]) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in org_domains)


async def run_scan(engine: AsyncEngine, vault: Vault, ref: UserRef, source: WorkspaceSource) -> dict[str, Any]:
    """Runs the full header pass and replaces the user's Sources index. Returns the counts."""
    async with user_tx(engine, ref) as conn:
        scan_id = (
            await conn.execute(
                text(
                    "insert into vanimo.source_scans (tenant_id, owner_user_id, source_kind, status) "
                    "values (:t, :u, :k, 'running') returning id"
                ),
                {"t": ref.tenant_id, "u": ref.user_id, "k": source.kind},
            )
        ).scalar_one()
    try:
        profile = await source.profile()
        org_domains = await source.org_domains()
        idx = await _collect(source, profile.email or "", datetime.now(UTC))
        counts = await _store(engine, vault, ref, idx, org_domains, scan_id, record_org=source.kind == "graph")
    except Exception as exc:
        async with user_tx(engine, ref) as conn:
            await conn.execute(
                text(
                    "update vanimo.source_scans set status = 'failed', finished_at = now(), error_code = :e "
                    "where id = :id"
                ),
                {"e": str(getattr(exc, "code", None) or type(exc).__name__)[:80], "id": scan_id},
            )
        log.warning("scan.failed", error_type=type(exc).__name__)
        raise
    log.info("scan.done", count=counts["messages"])
    return counts


async def _store(
    engine: AsyncEngine,
    vault: Vault,
    ref: UserRef,
    idx: _Index,
    org_domains: frozenset[str],
    scan_id: Any,
    *,
    record_org: bool,
) -> dict[str, Any]:
    async with user_tx(engine, ref) as conn:
        # Under the per-user lock, with the words as they are *now*: a word added while the
        # header pass ran is applied here, and a scrub can't interleave with this replace.
        await lock_user_controls(conn, ref)
        matcher = await load_matcher(conn, vault, ref)
        if not record_org:
            # The sample workspace's fictional domain is recorded only in the local (password) tenant,
            # never in a real organisation's tenant.
            tenant_key = (await conn.execute(text("select entra_tenant_id from vanimo.tenants"))).scalar_one()
            record_org = tenant_key == "local"
        return await _replace_index(conn, vault, ref, idx, matcher, org_domains, scan_id, record_org)


async def _replace_index(
    conn: Any,
    vault: Vault,
    ref: UserRef,
    idx: _Index,
    matcher: Matcher,
    org_domains: frozenset[str],
    scan_id: Any,
    record_org: bool,
) -> dict[str, Any]:
    h = hasher_for(vault, ref)
    t, u = ref.tenant_id, ref.user_id
    owner = {"t": t, "u": u}

    def enc(value: str | None, purpose: str, mask: bool = True) -> str | None:
        if mask:
            value, _ = matcher.mask(value)  # never-send words never reach storage
        return vault.encrypt_user(t, u, value, purpose)

    people, person_ids = [], {}
    for p in idx.people.values():
        pid = uuid.uuid4()
        person_ids[p.email] = pid
        domain = p.email.rsplit("@", 1)[-1]
        people.append(
            {
                **owner,
                "id": pid,
                "k": h("person", p.email),
                "dh": h("domain", domain),
                "e": enc(p.email, "email", mask=False),
                "n": enc(p.name, "name"),
                "d": enc(domain, "domain", mask=False),
                "int": _is_internal(domain, org_domains),
                "cons": domain in CONSUMER_DOMAINS,
                "s": p.sent,
                "c": p.chats,
                "m": p.meetings,
                "l": p.last,
            }
        )
    threads, thread_ids = [], {}
    for conv, th in idx.threads.items():
        tid = uuid.uuid4()
        thread_ids[conv] = tid
        threads.append(
            {
                **owner,
                "id": tid,
                "k": h("thread", conv),
                "s": enc(th["subject"], "subject"),
                "c": th["count"],
                "l": th["last"],
                "f": th["forward"],
            }
        )
    messages, message_links = [], []
    for m in idx.messages:
        mid = uuid.uuid4()
        messages.append(
            {**owner, "id": mid, "k": h("message", m["id"]), "th": thread_ids[m["conv"]], "s": m["sent_at"]}
        )
        message_links += [{**owner, "a": mid, "p": person_ids[e]} for e in dict.fromkeys(m["people"])]
    chats, chat_links = [], []
    for c in idx.chats:
        cid = uuid.uuid4()
        chats.append(
            {
                **owner,
                "id": cid,
                "k": h("chat", c["id"]),
                "ty": c["type"],
                "tp": enc(c["topic"], "topic"),
                "lb": enc(c["label"], "chat_label"),
                "mc": len(c["members"]),
                "hd": c["hidden"],
                "la": c["last"],
            }
        )
        chat_links += [{**owner, "a": cid, "p": person_ids[e]} for e in dict.fromkeys(c["members"])]
    meetings, meeting_links = [], []
    for mt in idx.meetings:
        mtid = uuid.uuid4()
        meetings.append(
            {
                **owner,
                "id": mtid,
                "k": h("meeting", mt["id"]),
                "sh": h("series", mt["series"]) if mt["series"] else None,
                "s": enc(mt["subject"], "subject"),
                "st": mt["start"],
                "pr": mt["private"],
                "on": mt["online"],
                "org": mt["organizer"],
                "ac": len(mt["people"]),
            }
        )
        meeting_links += [{**owner, "a": mtid, "p": person_ids[e]} for e in mt["people"]]

    inserts = [
        (
            "insert into vanimo.source_people (id, tenant_id, owner_user_id, key_hash, domain_hash, email_enc, "
            "name_enc, domain_enc, is_internal, is_consumer, sent_count, chat_count, meeting_count, "
            "last_contact_at) values (:id, :t, :u, :k, :dh, :e, :n, :d, :int, :cons, :s, :c, :m, :l)",
            people,
        ),
        (
            "insert into vanimo.source_threads (id, tenant_id, owner_user_id, key_hash, subject_enc, message_count, "
            "last_sent_at, is_forward) values (:id, :t, :u, :k, :s, :c, :l, :f)",
            threads,
        ),
        (
            "insert into vanimo.source_messages (id, tenant_id, owner_user_id, key_hash, thread_id, sent_at) values "
            "(:id, :t, :u, :k, :th, :s)",
            messages,
        ),
        (
            "insert into vanimo.source_message_people (tenant_id, owner_user_id, message_id, person_id) values "
            "(:t, :u, :a, :p)",
            message_links,
        ),
        (
            "insert into vanimo.source_chats (id, tenant_id, owner_user_id, key_hash, chat_type, topic_enc, label_enc, "
            "member_count, hidden, last_activity_at) values (:id, :t, :u, :k, :ty, :tp, :lb, :mc, :hd, :la)",
            chats,
        ),
        (
            "insert into vanimo.source_chat_people (tenant_id, owner_user_id, chat_id, person_id) values "
            "(:t, :u, :a, :p)",
            chat_links,
        ),
        (
            "insert into vanimo.source_meetings (id, tenant_id, owner_user_id, key_hash, series_hash, subject_enc, "
            "start_at, is_private, is_online, is_organizer, attendee_count) values (:id, :t, :u, :k, :sh, :s, :st, "
            ":pr, :on, :org, :ac)",
            meetings,
        ),
        (
            "insert into vanimo.source_meeting_people (tenant_id, owner_user_id, meeting_id, person_id) values "
            "(:t, :u, :a, :p)",
            meeting_links,
        ),
    ]
    counts = {
        "people": len(people),
        "threads": len(threads),
        "messages": len(messages),
        "chats": len(chats),
        "meetings": len(meetings),
        "org_domain_hashes": sorted({h("domain", d) for d in org_domains}),
    }
    for table in ("source_threads", "source_chats", "source_meetings", "source_people"):
        # Messages and link rows cascade from these.
        await conn.execute(text(f"delete from vanimo.{table}"))  # noqa: S608 - constant table names
    for sql, rows in inserts:
        if rows:
            await conn.execute(text(sql), rows)
    if record_org:
        await conn.execute(
            text("select vanimo_private.record_org_domains(cast(:h as text[]))"), {"h": counts["org_domain_hashes"]}
        )
    await conn.execute(
        text(
            "update vanimo.source_scans set status = 'done', finished_at = now(), counts = cast(:c as jsonb) "
            "where id = :id"
        ),
        {"c": json.dumps(counts), "id": scan_id},
    )
    return counts
