"""Workspace metadata from Microsoft Graph (delegated, as the signed-in user).

Every `$select` goes through `assert_metadata_only`: this module never reads message text.
Calls follow `docs/research/12` §9.2 (header pass).
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from vanimo.graph import metadata
from vanimo.graph.client import GraphClient, GraphError
from vanimo.redaction.parse import html_to_text
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

SENT_FIELDS = (
    "id",
    "conversationId",
    "subject",
    "sentDateTime",
    "toRecipients",
    "ccRecipients",
    "bccRecipients",
    "from",
    "sender",
)
EVENT_FIELDS = (
    "id",
    "subject",
    "start",
    "end",
    "organizer",
    "attendees",
    "seriesMasterId",
    "isOnlineMeeting",
    "onlineMeeting",
    "sensitivity",
    "isOrganizer",
    "iCalUId",
    "type",
)
GRAPH_MEMBER_PAGE = 25  # chats list returns at most 25 members per chat


def _addr(recipient: dict[str, Any] | None) -> Address | None:
    email = ((recipient or {}).get("emailAddress") or {}).get("address")
    if not email:
        return None
    return Address(email=email.lower(), name=(recipient or {}).get("emailAddress", {}).get("name"))


def _addrs(items: list[dict[str, Any]] | None) -> tuple[Address, ...]:
    return tuple(a for a in (_addr(i) for i in items or []) if a)


EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _graph_time(obj: dict[str, Any]) -> datetime:
    # calendarView returns {"dateTime": "...", "timeZone": "UTC"} when Prefer outlook.timezone=UTC.
    return datetime.fromisoformat(obj["dateTime"].split(".")[0] + "+00:00")


def _member(m: dict[str, Any]) -> Address | None:
    email = (m.get("email") or "").lower()
    if not email:
        return None
    return Address(email=email, name=m.get("displayName"))


class GraphSource:
    kind = "graph"

    def __init__(self, graph: GraphClient) -> None:
        self._g = graph

    def for_background(self) -> GraphSource:
        return GraphSource(self._g.for_background())

    async def profile(self) -> Profile:
        me = await metadata.me(self._g)
        email = (me.get("mail") or me.get("userPrincipalName") or "").lower() or None
        return Profile(me.get("displayName"), email, me.get("jobTitle"), me.get("department"), me.get("id"))

    async def manager(self) -> Profile | None:
        mgr = await metadata.manager(self._g)
        return Profile(mgr.get("displayName"), None, mgr.get("jobTitle")) if mgr else None

    async def recent_sent(self, top: int = 5) -> list[SentHeader]:
        return [self._header(m) for m in await metadata.recent_sent_headers(self._g, top=top)]

    @staticmethod
    def _header(m: dict[str, Any]) -> SentHeader:
        return SentHeader(
            id=m["id"],
            conversation_id=m.get("conversationId") or m["id"],
            subject=m.get("subject"),
            sent_at=_dt(m.get("sentDateTime")) or EPOCH,
            to=_addrs(m.get("toRecipients")),
            cc=_addrs(m.get("ccRecipients")),
            bcc=_addrs(m.get("bccRecipients")),
            sender=_addr(m.get("from")),  # the scan drops it when it's the user themselves
        )

    async def sent_headers(self) -> AsyncIterator[SentHeader]:
        async for page in self._g.pages(
            "me/mailFolders/sentitems/messages/delta",
            {"$select": metadata.assert_metadata_only(SENT_FIELDS)},
            max_pages=10_000,
            headers={"Prefer": 'odata.maxpagesize=100, IdType="ImmutableId"'},
        ):
            for m in page.get("value", []):
                if "@removed" not in m:
                    yield self._header(m)

    async def chats(self) -> AsyncIterator[Chat]:
        # Never expand lastMessagePreview: it carries message text. (No $select: its support on
        # /me/chats is unverified, and the default chat properties carry no message content.)
        async for page in self._g.pages("me/chats", {"$expand": "members", "$top": "50"}, max_pages=1_000):
            for c in page.get("value", []):
                members_raw = c.get("members") or []
                complete = True
                if len(members_raw) >= GRAPH_MEMBER_PAGE:
                    try:
                        full: list[dict[str, Any]] = []
                        async for mp in self._g.pages(f"chats/{c['id']}/members", max_pages=100):
                            full += mp.get("value", [])
                        members_raw = full or members_raw
                    except GraphError:
                        complete = False  # we can't see everyone: the chat's content is never read
                if any(not _member(m) for m in members_raw):
                    complete = False  # a guest or anonymous member without an address
                yield Chat(
                    id=c["id"],
                    chat_type=c.get("chatType", "group")
                    if c.get("chatType") in ("oneOnOne", "group", "meeting")
                    else "group",
                    topic=c.get("topic"),
                    members=tuple(a for a in (_member(m) for m in members_raw) if a),
                    last_activity_at=_dt(c.get("lastUpdatedDateTime")),
                    hidden=bool((c.get("viewpoint") or {}).get("isHidden")),
                    join_url=(c.get("onlineMeetingInfo") or {}).get("joinWebUrl"),
                    members_complete=complete,
                )

    async def events(self, start: datetime, end: datetime) -> AsyncIterator[Event]:
        async for page in self._g.pages(
            "me/calendarView",
            {
                "startDateTime": start.isoformat(),
                "endDateTime": end.isoformat(),
                "$select": metadata.assert_metadata_only(EVENT_FIELDS),
                "$top": "100",
            },
            max_pages=1_000,
            headers={"Prefer": 'outlook.timezone="UTC"'},
        ):
            for e in page.get("value", []):
                yield Event(
                    id=e["id"],
                    subject=e.get("subject"),
                    start=_graph_time(e["start"]),
                    end=_graph_time(e["end"]),
                    organizer=_addr(e.get("organizer")),
                    attendees=_addrs(e.get("attendees")),
                    series_id=e.get("seriesMasterId"),
                    is_online=bool(e.get("isOnlineMeeting")),
                    is_private=e.get("sensitivity") == "private",
                    is_organizer=bool(e.get("isOrganizer")),
                    join_url=(e.get("onlineMeeting") or {}).get("joinUrl"),
                )

    async def direct_reports(self) -> list[Address]:
        page = await self._g.get("me/directReports", {"$select": "mail,userPrincipalName,displayName"})
        out = []
        for r in page.get("value", []):
            email = (r.get("mail") or r.get("userPrincipalName") or "").lower()
            if email:
                out.append(Address(email=email, name=r.get("displayName")))
        return out

    async def _me(self) -> Profile:
        if not hasattr(self, "_profile"):
            self._profile = await self.profile()
        return self._profile

    def _content(self, m: dict[str, Any], me: Profile) -> MessageContent:
        sender = _addr(m.get("from")) or Address(email="")
        unique, hidden_u = _body_text(m.get("uniqueBody"))
        full, hidden_f = _body_text(m.get("body"))
        quoted = full.replace(unique, "", 1).strip() if unique else ""
        return MessageContent(
            id=m["id"],
            conversation_id=m.get("conversationId") or m["id"],
            subject=m.get("subject"),
            sent_at=_dt(m.get("sentDateTime")) or EPOCH,
            sender=sender,
            to=_addrs(m.get("toRecipients")),
            cc=_addrs(m.get("ccRecipients")),
            direction="sent" if me.email and sender.email == me.email else "received",
            body=unique or full,
            quoted=quoted,
            hidden=hidden_u or hidden_f,
        )

    async def thread_headers(self, conversation_id: str) -> list[MessageHeader]:
        """Every message of a conversation, metadata only (no body): the engine decides first."""
        me = await self._me()
        out: list[MessageHeader] = []
        async for page in self._g.pages(
            "me/messages",
            {
                "$filter": f"conversationId eq {_odata(conversation_id)}",
                "$select": metadata.assert_metadata_only(THREAD_FIELDS),
                "$top": "50",
            },
            max_pages=40,
            headers={"Prefer": 'IdType="ImmutableId"'},
        ):
            for m in page.get("value", []):
                sender = _addr(m.get("from")) or Address(email="")
                out.append(
                    MessageHeader(
                        id=m["id"],
                        conversation_id=m.get("conversationId") or conversation_id,
                        sent_at=_dt(m.get("sentDateTime")) or EPOCH,
                        sender=sender,
                        to=_addrs(m.get("toRecipients")),
                        cc=_addrs(m.get("ccRecipients")),
                        direction="sent" if me.email and sender.email == me.email else "received",
                    )
                )
        return sorted(out, key=lambda h: h.sent_at)

    async def message(self, message_id: str) -> MessageContent | None:
        # HTML bodies (not Graph's text conversion), so hidden content is found and dropped here.
        try:
            m = await self._g.get(
                f"me/messages/{_safe_id(message_id)}", {"$select": CONTENT_FIELDS}, headers=IMMUTABLE_IDS
            )
        except GraphError as exc:
            if exc.status == 404:
                return None
            raise
        return self._content(m, await self._me())

    async def chat_messages(self, chat_id: str) -> AsyncIterator[ChatMessage]:
        me = await self._me()
        safe = _safe_id(chat_id, _CHAT_ID)
        # Senders are matched to the roster by directory ID, so person rules (keyed by address)
        # apply to them. Someone not on the roster (left the chat) gets no address: never trusted.
        roster: dict[str, str] = {}
        async for page in self._g.pages(f"chats/{safe}/members", max_pages=100):
            for mem in page.get("value", []):
                if mem.get("userId") and mem.get("email"):
                    roster[mem["userId"]] = mem["email"].lower()
        async for page in self._g.pages(f"chats/{safe}/messages", {"$top": "50"}, max_pages=20):
            for m in page.get("value", []):
                if m.get("messageType") != "message" or m.get("deletedDateTime"):
                    continue
                user = ((m.get("from") or {}).get("user")) or {}
                text, _hidden = _body_text(m.get("body"))
                yield ChatMessage(
                    id=m["id"],
                    chat_id=chat_id,
                    sender=Address(email=roster.get(user.get("id") or "", ""), name=user.get("displayName")),
                    created_at=_dt(m.get("createdDateTime")) or EPOCH,
                    text=text,
                    from_me=bool(me.id) and user.get("id") == me.id,
                )

    async def event_agenda(self, event_id: str) -> str | None:
        e = await self._g.get(f"me/events/{_safe_id(event_id)}", {"$select": "body"})
        text, _ = _body_text(e.get("body"))
        return text or None

    async def org_domains(self) -> frozenset[str]:
        org = await self._g.get("organization", {"$select": "verifiedDomains"})
        return frozenset(
            d["name"].lower() for o in org.get("value", []) for d in o.get("verifiedDomains", []) if d.get("name")
        )


# --- content reads (callers must pass the onboarding gate; see base.py) -------------------------
CONTENT_FIELDS = "id,conversationId,subject,sentDateTime,from,toRecipients,ccRecipients,uniqueBody,body"
THREAD_FIELDS = ("id", "conversationId", "sentDateTime", "from", "toRecipients", "ccRecipients")
IMMUTABLE_IDS = {"Prefer": 'IdType="ImmutableId"'}


def _body_text(body: dict[str, Any] | None) -> tuple[str, bool]:
    """Text of a Graph itemBody, and whether hidden HTML was dropped. Only HTML is parsed as HTML."""
    content = (body or {}).get("content") or ""
    if (body or {}).get("contentType", "html").lower() == "html":
        return html_to_text(content)
    return content.strip(), False


_GRAPH_ID = re.compile(r"^[A-Za-z0-9_=\-]{1,512}$")
_CHAT_ID = re.compile(r"^[A-Za-z0-9:@._\-]{1,256}$")


def _safe_id(value: str, pattern: re.Pattern[str] = _GRAPH_ID) -> str:
    if not pattern.match(value):
        raise ValueError("invalid Graph id")
    return value


def _odata(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
