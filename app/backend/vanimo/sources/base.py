"""Workspace sources: where a user's Microsoft 365 *metadata* comes from.

Two implementations behind one interface:
  * GraphSource  — the user's real mailbox, chats and calendar through Microsoft Graph
                   (needs a Microsoft sign-in, for the On-Behalf-Of token);
  * SampleSource — a synthetic workspace, so every feature can be built and demoed while
                   Entra/Graph access is pending (founder decision, 2026-10-13).

Everything here is metadata (headers, rosters, calendar fields). Message text is never
part of this interface; content reads arrive in M2 behind the onboarding gate.
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


class WorkspaceSource(Protocol):
    kind: SourceKind

    async def profile(self) -> Profile: ...

    async def manager(self) -> Profile | None: ...

    async def recent_sent(self, top: int = 5) -> list[SentHeader]: ...

    def sent_headers(self) -> AsyncIterator[SentHeader]: ...

    def chats(self) -> AsyncIterator[Chat]: ...

    def events(self, start: datetime, end: datetime) -> AsyncIterator[Event]: ...

    async def org_domains(self) -> frozenset[str]: ...
