"""Workspace metadata from Microsoft Graph (delegated, as the signed-in user).

Every `$select` goes through `assert_metadata_only`: this module never reads message text.
Calls follow `docs/research/12` §9.2 (header pass).
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from vanimo.graph import metadata
from vanimo.graph.client import GraphClient, GraphError
from vanimo.redaction.parse import html_to_text
from vanimo.sources.base import (
    Address,
    Chat,
    ChatMessage,
    DraftItemState,
    Event,
    InboxHeader,
    MessageContent,
    MessageHeader,
    PlacedDraft,
    Profile,
    SentHeader,
    Transcript,
    TranscriptRef,
    TranscriptsUnavailable,
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
VTT = "text/vtt"
UNATTRIBUTED = "application/vnd.microsoft.graph.transcript+text"  # Accept header only, not $format
MAX_TRANSCRIPT_BYTES = 4_000_000


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
        self._meetings: dict[str, str | None] = {}  # join link -> online meeting ID (a series shares one)

    def for_background(self) -> GraphSource:
        return GraphSource(self._g.for_background())

    async def profile(self) -> Profile:
        me = await metadata.me(self._g)
        email = (me.get("mail") or me.get("userPrincipalName") or "").lower() or None
        return Profile(me.get("displayName"), email, me.get("jobTitle"), me.get("department"), me.get("id"))

    async def manager(self) -> Profile | None:
        mgr = await metadata.manager(self._g)
        if not mgr:
            return None
        email = (mgr.get("mail") or mgr.get("userPrincipalName") or "").lower() or None
        return Profile(mgr.get("displayName"), email, mgr.get("jobTitle"))

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

    async def sent_headers(self, since: datetime | None = None) -> AsyncIterator[SentHeader]:
        if since is None:
            path = "me/mailFolders/sentitems/messages/delta"
            params = {"$select": metadata.assert_metadata_only(SENT_FIELDS)}
        else:  # only what was sent after `since` (the commitments scan), oldest first
            path = "me/mailFolders/sentitems/messages"
            params = {
                "$select": metadata.assert_metadata_only(SENT_FIELDS),
                "$filter": f"sentDateTime gt {since.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
                "$orderby": "sentDateTime asc",
                "$top": "50",
            }
        async for page in self._g.pages(
            path,
            params,
            max_pages=10_000 if since is None else 20,
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
                yield await self._chat(c)

    async def chat(self, chat_id: str) -> Chat | None:
        try:
            c = await self._g.get(f"me/chats/{_safe_id(chat_id, _CHAT_ID)}", {"$expand": "members"})
        except GraphError as exc:
            if exc.status == 404:
                return None
            raise
        return await self._chat(c)

    async def _chat(self, c: dict[str, Any]) -> Chat:
        members_raw = c.get("members") or []
        complete = True
        if len(members_raw) >= GRAPH_MEMBER_PAGE:
            try:
                full: list[dict[str, Any]] = []
                async for mp in self._g.pages(f"chats/{c['id']}/members", max_pages=100):  # an ID from Graph itself
                    full += mp.get("value", [])
                members_raw = full or members_raw
            except GraphError:
                complete = False  # we can't see everyone: the chat's content is never read
        if any(not _member(m) for m in members_raw):
            complete = False  # a guest or anonymous member without an address
        return Chat(
            id=c["id"],
            chat_type=c.get("chatType", "group") if c.get("chatType") in ("oneOnOne", "group", "meeting") else "group",
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
                        is_draft=bool(m.get("isDraft")),
                        reply_to=_addrs(m.get("replyTo")),
                    )
                )
        return sorted(out, key=lambda h: h.sent_at)

    async def recent_received(self, top: int = 25) -> list[InboxHeader]:
        out: dict[str, InboxHeader] = {}
        for m in await metadata.recent_inbox_headers(self._g, top=min(top * 2, 100)):
            conv = m.get("conversationId") or m["id"]
            if conv in out:
                continue  # newest first: the first one seen is the latest of its conversation
            out[conv] = InboxHeader(
                id=m["id"],
                conversation_id=conv,
                subject=m.get("subject"),
                received_at=_dt(m.get("receivedDateTime")) or EPOCH,
                sender=_addr(m.get("from")) or Address(email=""),
                to=_addrs(m.get("toRecipients")),
                cc=_addrs(m.get("ccRecipients")),
            )
        return list(out.values())[:top]

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

    async def chat_messages(self, chat_id: str, since: datetime | None = None) -> AsyncIterator[ChatMessage]:
        me = await self._me()
        safe = _safe_id(chat_id, _CHAT_ID)
        # Senders are matched to the roster by directory ID, so person rules (keyed by address)
        # apply to them. Someone not on the roster (left the chat) gets no address: never trusted.
        roster: dict[str, str] = {}
        async for page in self._g.pages(f"chats/{safe}/members", max_pages=100):
            for mem in page.get("value", []):
                if mem.get("userId") and mem.get("email"):
                    roster[mem["userId"]] = mem["email"].lower()
        params = {"$top": "50"}
        if since is not None:
            # Graph filters chat messages only on lastModifiedDateTime, and only with a matching
            # $orderby (newest first); created-before-since messages edited later are dropped below.
            params |= {
                "$orderby": "lastModifiedDateTime desc",
                "$filter": f"lastModifiedDateTime gt {since.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
            }
        async for page in self._g.pages(f"chats/{safe}/messages", params, max_pages=20):
            for m in page.get("value", []):
                if m.get("messageType") != "message" or m.get("deletedDateTime"):
                    continue
                user = ((m.get("from") or {}).get("user")) or {}
                created = _dt(m.get("createdDateTime")) or EPOCH
                if since is not None and created <= since:
                    continue
                text, _hidden = _body_text(m.get("body"))
                yield ChatMessage(
                    id=m["id"],
                    chat_id=chat_id,
                    sender=Address(email=roster.get(user.get("id") or "", ""), name=user.get("displayName")),
                    created_at=created,
                    text=text,
                    from_me=bool(me.id) and user.get("id") == me.id,
                )

    async def event_agenda(self, event_id: str) -> str | None:
        e = await self._g.get(f"me/events/{_safe_id(event_id)}", {"$select": "body"})
        text, _ = _body_text(e.get("body"))
        return text or None

    # --- meeting transcripts (M6): delegated, for the organiser and invited attendees -----------
    async def _meeting_id(self, join_url: str) -> str | None:
        if join_url not in self._meetings:
            found = await self._g.get(
                "me/onlineMeetings", {"$filter": f"JoinWebUrl eq {_odata(join_url)}", "$select": "id"}
            )
            ids = [m.get("id") for m in found.get("value", []) if m.get("id")]
            self._meetings[join_url] = ids[0] if ids else None
        return self._meetings[join_url]

    async def meeting_transcripts(self, event: Event) -> list[TranscriptRef]:
        if not event.join_url:
            return []
        try:
            meeting = await self._meeting_id(event.join_url)
            if meeting is None:
                return []
            out = []
            async for page in self._g.pages(
                f"me/onlineMeetings/{_path_id(meeting)}/transcripts",
                {"$select": "id,createdDateTime,endDateTime"},
                max_pages=20,
            ):
                for t in page.get("value", []):
                    created = _dt(t.get("createdDateTime"))
                    if t.get("id") and created:
                        out.append(TranscriptRef(t["id"], meeting, created, _dt(t.get("endDateTime"))))
            return out
        except GraphError as exc:
            raise _unavailable(exc) from exc

    async def transcript(self, ref: TranscriptRef) -> Transcript:
        from vanimo.memory.vtt import parse

        path = f"me/onlineMeetings/{_path_id(ref.meeting_id)}/transcripts/{_path_id(ref.id)}/content"
        attributed = True
        try:
            try:
                resp = await self._g.request("GET", path, headers={"Accept": VTT})
            except GraphError as exc:
                if exc.inner != "SpeakerAttributionNotAllowed":
                    raise
                # The organisation turned speaker attribution off: the same transcript without names.
                attributed = False
                resp = await self._g.request("GET", path, headers={"Accept": UNATTRIBUTED})
        except GraphError as exc:
            raise _unavailable(exc) from exc
        if len(resp.content) > MAX_TRANSCRIPT_BYTES:
            raise TranscriptsUnavailable("too_large")
        return Transcript(ref, attributed, tuple(parse(resp.text, attributed=attributed)))

    # --- drafts in the mailbox (M4) ---------------------------------------------------------
    async def create_reply_draft(self, message_id: str, text: str, *, reply_all: bool) -> PlacedDraft:
        # `comment` puts the text above the quoted thread and keeps the thread intact (a body
        # replacement would drop it). Immutable IDs: the ID stays the same when the draft is sent.
        action = "createReplyAll" if reply_all else "createReply"
        resp = await self._g.request(
            "POST",
            f"me/messages/{_safe_id(message_id)}/{action}",
            json={"comment": text},
            headers=IMMUTABLE_IDS,
            idempotent=False,
        )
        d = resp.json()
        return PlacedDraft(id=d["id"], web_link=d.get("webLink"))

    async def set_draft_recipients(self, item_id: str, to: list[Address], cc: list[Address]) -> None:
        def rec(a: Address) -> dict[str, Any]:
            return {"emailAddress": {"address": a.email, **({"name": a.name} if a.name else {})}}

        await self._g.patch(
            f"me/messages/{_safe_id(item_id)}",
            json={"toRecipients": [rec(a) for a in to], "ccRecipients": [rec(a) for a in cc]},
            headers=IMMUTABLE_IDS,
        )

    async def draft_state(self, item_id: str) -> DraftItemState:
        try:
            m = await self._g.get(
                f"me/messages/{_safe_id(item_id)}",
                {"$select": metadata.assert_metadata_only(("id", "isDraft", "lastModifiedDateTime"))},
                headers=IMMUTABLE_IDS,
            )
        except GraphError as exc:
            if exc.status == 404:
                return DraftItemState(exists=False)
            raise
        return DraftItemState(True, bool(m.get("isDraft")), _dt(m.get("lastModifiedDateTime")))

    async def delete_draft(self, item_id: str) -> bool:
        state = await self.draft_state(item_id)
        if not (state.exists and state.is_draft):
            return False  # never delete something the user sent
        await self._g.delete(f"me/messages/{_safe_id(item_id)}")
        return True

    async def org_domains(self) -> frozenset[str]:
        org = await self._g.get("organization", {"$select": "verifiedDomains"})
        return frozenset(
            d["name"].lower() for o in org.get("value", []) for d in o.get("verifiedDomains", []) if d.get("name")
        )


# --- content reads (callers must pass the onboarding gate; see base.py) -------------------------
CONTENT_FIELDS = "id,conversationId,subject,sentDateTime,from,toRecipients,ccRecipients,uniqueBody,body"
THREAD_FIELDS = (
    "id",
    "conversationId",
    "sentDateTime",
    "from",
    "toRecipients",
    "ccRecipients",
    "isDraft",
    "replyTo",
)
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


_MEETING_ID = re.compile(r"^[A-Za-z0-9+/=_\-]{1,2048}$")


def _path_id(value: str) -> str:
    """Online meeting and transcript IDs are base64 (may hold '/' or '+'): validated, then escaped."""
    return quote(_safe_id(value, _MEETING_ID), safe="")


def _unavailable(exc: GraphError) -> TranscriptsUnavailable:
    if exc.inner == "GraphAccessToTranscriptsDisabled":
        return TranscriptsUnavailable("disabled")
    if exc.status == 404:
        return TranscriptsUnavailable("not_found")
    if exc.status in (401, 403):
        return TranscriptsUnavailable("permission")
    if exc.status == 410:
        return TranscriptsUnavailable("expired")
    return TranscriptsUnavailable(f"graph_{exc.status}")


def _odata(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
