"""Workspace metadata from Microsoft Graph (delegated, as the signed-in user).

Every `$select` goes through `assert_metadata_only`: this module never reads message text.
Calls follow `docs/research/12` §9.2 (header pass).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from vanimo.graph import metadata
from vanimo.graph.client import GraphClient, GraphError
from vanimo.sources.base import Address, Chat, Event, Profile, SentHeader

SENT_FIELDS = (
    "id",
    "conversationId",
    "subject",
    "sentDateTime",
    "toRecipients",
    "ccRecipients",
    "bccRecipients",
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
)
GRAPH_MEMBER_PAGE = 25  # chats list returns at most 25 members per chat


def _addr(recipient: dict[str, Any] | None) -> Address | None:
    email = ((recipient or {}).get("emailAddress") or {}).get("address")
    if not email:
        return None
    return Address(email=email.lower(), name=(recipient or {}).get("emailAddress", {}).get("name"))


def _addrs(items: list[dict[str, Any]] | None) -> tuple[Address, ...]:
    return tuple(a for a in (_addr(i) for i in items or []) if a)


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

    async def profile(self) -> Profile:
        me = await metadata.me(self._g)
        email = (me.get("mail") or me.get("userPrincipalName") or "").lower() or None
        return Profile(me.get("displayName"), email, me.get("jobTitle"), me.get("department"))

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
            sent_at=_dt(m.get("sentDateTime")) or datetime.min,
            to=_addrs(m.get("toRecipients")),
            cc=_addrs(m.get("ccRecipients")),
            bcc=_addrs(m.get("bccRecipients")),
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
        # Never expand lastMessagePreview: it carries message text.
        async for page in self._g.pages(
            "me/chats",
            {"$expand": "members", "$select": "id,chatType,topic,lastUpdatedDateTime,viewpoint", "$top": "50"},
            max_pages=1_000,
        ):
            for c in page.get("value", []):
                members_raw = c.get("members") or []
                if len(members_raw) >= GRAPH_MEMBER_PAGE:
                    try:
                        full = await self._g.get(f"chats/{c['id']}/members")
                        members_raw = full.get("value", members_raw)
                    except GraphError:
                        pass
                yield Chat(
                    id=c["id"],
                    chat_type=c.get("chatType", "group")
                    if c.get("chatType") in ("oneOnOne", "group", "meeting")
                    else "group",
                    topic=c.get("topic"),
                    members=tuple(a for a in (_member(m) for m in members_raw) if a),
                    last_activity_at=_dt(c.get("lastUpdatedDateTime")),
                    hidden=bool((c.get("viewpoint") or {}).get("isHidden")),
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

    async def org_domains(self) -> frozenset[str]:
        org = await self._g.get("organization", {"$select": "verifiedDomains"})
        return frozenset(
            d["name"].lower() for o in org.get("value", []) for d in o.get("verifiedDomains", []) if d.get("name")
        )
