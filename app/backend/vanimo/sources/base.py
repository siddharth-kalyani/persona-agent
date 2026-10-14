"""Workspace sources: where a user's Microsoft 365 *metadata* comes from.

Two implementations behind one interface:
  * GraphSource  — the user's real mailbox, chats and calendar through Microsoft Graph
                   (needs a Microsoft sign-in, for the On-Behalf-Of token);
  * SampleSource — a synthetic workspace, so every feature can be built and demoed while
                   Entra/Graph access is pending (founder decision, 2026-10-13).

Metadata methods (headers, rosters, calendar fields) are safe before the review step. The
content methods (`message`, `chat_messages`, `event_agenda`) read message text: callers must
pass the onboarding gate first (`vanimo.gates.require_review_done`) and fetch only items the
exclusion engine allowed from their metadata (`thread_headers`, rosters): two-phase fetch,
architecture §6.5 X2.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol

SourceKind = Literal["graph", "sample"]

# Pre-flagged for review: personal mail, not work (architecture §6.5).
CONSUMER_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "outlook.com",
        "hotmail.com",
        "live.com",
        "yahoo.com",
        "yahoo.co.in",
        "icloud.com",
        "me.com",
        "aol.com",
        "proton.me",
        "protonmail.com",
        "rediffmail.com",
        "zoho.com",
    }
)


@dataclass(frozen=True)
class Address:
    email: str
    name: str | None = None

    @property
    def domain(self) -> str:
        return self.email.rsplit("@", 1)[-1].lower()


@dataclass(frozen=True)
class Profile:
    display_name: str | None
    email: str | None = None
    job_title: str | None = None
    department: str | None = None
    id: str | None = None  # directory object ID (identifies the user's own chat messages)


@dataclass(frozen=True)
class SentHeader:
    id: str
    conversation_id: str
    subject: str | None
    sent_at: datetime
    to: tuple[Address, ...] = ()
    cc: tuple[Address, ...] = ()
    bcc: tuple[Address, ...] = ()
    # Set when someone else is the "from" (sent on behalf of / as a delegate): a participant too.
    sender: Address | None = None

    @property
    def recipients(self) -> tuple[Address, ...]:
        return self.to + self.cc + self.bcc

    @property
    def participants(self) -> tuple[Address, ...]:
        return self.recipients + ((self.sender,) if self.sender else ())


@dataclass(frozen=True)
class Chat:
    id: str
    chat_type: Literal["oneOnOne", "group", "meeting"]
    topic: str | None
    members: tuple[Address, ...]
    last_activity_at: datetime | None = None
    hidden: bool = False
    # Meeting chats: the meeting's join link, which ties the chat to its calendar event (and series).
    join_url: str | None = field(default=None, repr=False)
    # False when the full roster couldn't be read, or a member has no address (guest, anonymous):
    # the engine can't vouch for who is in the chat, so its content is never read (fail-closed).
    members_complete: bool = True


@dataclass(frozen=True)
class Event:
    id: str
    subject: str | None
    start: datetime
    end: datetime
    organizer: Address | None
    attendees: tuple[Address, ...] = ()
    series_id: str | None = None
    is_online: bool = False
    is_private: bool = False
    is_organizer: bool = False
    join_url: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class MessageContent:
    """One email with its text (L0 — in memory only, never stored as is)."""

    id: str
    conversation_id: str
    subject: str | None
    sent_at: datetime
    sender: Address
    to: tuple[Address, ...]
    cc: tuple[Address, ...]
    direction: Literal["sent", "received"]
    body: str  # the author's own words in this message (Graph `uniqueBody`)
    quoted: str = ""  # earlier messages quoted below it, if any
    hidden: bool = False  # hidden HTML (display:none, white-on-white) was found and dropped

    @property
    def recipients(self) -> tuple[Address, ...]:
        return self.to + self.cc


@dataclass(frozen=True)
class MessageHeader:
    """One message of a thread, metadata only: the engine decides on this before any text is read."""

    id: str
    conversation_id: str
    sent_at: datetime
    sender: Address
    to: tuple[Address, ...]
    cc: tuple[Address, ...]
    direction: Literal["sent", "received"]
    # An unsent draft in the conversation (for example the reply being written right now).
    is_draft: bool = False

    @property
    def participants(self) -> tuple[Address, ...]:
        return (self.sender, *self.to, *self.cc)


@dataclass(frozen=True)
class InboxHeader:
    """The latest received message of a conversation, metadata only (the drafting thread picker)."""

    id: str
    conversation_id: str
    subject: str | None
    received_at: datetime
    sender: Address
    to: tuple[Address, ...] = ()
    cc: tuple[Address, ...] = ()


@dataclass(frozen=True)
class PlacedDraft:
    """A reply draft Vanimo put in the user's Outlook Drafts folder (M4)."""

    id: str  # the mailbox item (immutable ID in Microsoft 365)
    web_link: str | None  # opens it in Outlook on the web


@dataclass(frozen=True)
class DraftItemState:
    """What became of a placed draft, from metadata only."""

    exists: bool
    is_draft: bool = False  # False once it was sent (the immutable ID follows it to Sent Items)
    modified_at: datetime | None = None  # None when unknown (the sample workspace)


@dataclass(frozen=True)
class ChatMessage:
    id: str
    chat_id: str
    sender: Address  # email "" when the sender couldn't be matched to the chat roster
    created_at: datetime
    text: str
    from_me: bool


class WorkspaceSource(Protocol):
    kind: SourceKind

    async def profile(self) -> Profile: ...

    async def manager(self) -> Profile | None: ...

    async def recent_sent(self, top: int = 5) -> list[SentHeader]: ...

    def sent_headers(self) -> AsyncIterator[SentHeader]: ...

    def chats(self) -> AsyncIterator[Chat]: ...

    def events(self, start: datetime, end: datetime) -> AsyncIterator[Event]: ...

    async def org_domains(self) -> frozenset[str]: ...

    async def direct_reports(self) -> list[Address]: ...

    async def thread_headers(self, conversation_id: str) -> list[MessageHeader]: ...

    async def recent_received(self, top: int = 25) -> list[InboxHeader]:
        """Conversations with recent received mail, newest first, one header each (metadata only)."""
        ...

    # --- content (behind the onboarding gate) ---------------------------------------------
    async def message(self, message_id: str) -> MessageContent | None: ...

    def chat_messages(self, chat_id: str) -> AsyncIterator[ChatMessage]: ...

    async def event_agenda(self, event_id: str) -> str | None: ...

    # --- drafts in the user's mailbox (M4; Mail.ReadWrite; never sends) ----------------------
    async def create_reply_draft(self, message_id: str, text: str, *, reply_all: bool) -> PlacedDraft:
        """A reply (or reply-all) draft to `message_id`, with `text` above the quoted thread."""
        ...

    async def draft_state(self, item_id: str) -> DraftItemState: ...

    async def delete_draft(self, item_id: str) -> bool:
        """Deletes the item only while it is still an unsent draft. True if deleted."""
        ...
