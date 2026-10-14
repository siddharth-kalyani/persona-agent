"""One exclusion engine for user rules and the organisation's rules (architecture §6.5, D9).

Decides on identifiers only, never on content. Any exclusion wins; users can add rules but
never lift the organisation's. Inputs are HMAC keys (see vanimo.vault), so the engine never
needs raw addresses at rest.

Organisation rules:
  * client accounts marked "excluded" — every conversation with one of their domains (and
    subdomains) is out, for everyone;
  * external mode "approved_only" — conversations with any external participant whose domain
    isn't in an "approved" account are out (internal domains are always fine).
User rules: person, domain, chat, thread, meeting occurrence, meeting series. A person rule
covers every chat the person is in, except chats the user explicitly unticked (D5). A meeting or
series rule also covers the meeting's chat (linked through the meeting's join link).
System: a chat whose full roster couldn't be read is excluded (fail-closed; nobody can lift it).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Literal

from vanimo.sources.base import Address, Chat, Event, SentHeader

RuleKind = Literal["person", "domain", "chat", "thread", "meeting", "series"]
Hasher = Callable[[str, str], str]  # (kind, normalised identifier) -> key hash


@dataclass(frozen=True)
class Reason:
    scope: Literal["user", "tenant"]
    kind: str  # rule kind, or "client_account" / "not_approved" for the organisation
    rule_id: str | None = None
    account_id: str | None = None


@dataclass(frozen=True)
class Decision:
    reasons: tuple[Reason, ...] = ()

    @property
    def excluded(self) -> bool:
        return bool(self.reasons)

    @property
    def by_tenant(self) -> bool:
        return any(r.scope == "tenant" for r in self.reasons)


@dataclass(frozen=True)
class UserRule:
    id: str
    kind: RuleKind
    key_hash: str
    except_chats: frozenset[str] = frozenset()  # chat hashes unticked for a person rule


@dataclass
class ExclusionEngine:
    hasher: Hasher
    user_rules: list[UserRule] = field(default_factory=list)  # person/domain rules may carry chat exceptions
    excluded_domains: dict[str, str] = field(default_factory=dict)  # domain hash -> client account id
    approved_domains: frozenset[str] = frozenset()
    external_mode: Literal["allow_all", "approved_only"] = "allow_all"
    org_domains: frozenset[str] = frozenset()  # hashes of the organisation's own domains
    self_email: str | None = None

    def __post_init__(self) -> None:
        self._by_kind: dict[str, dict[str, UserRule]] = {}
        for rule in self.user_rules:
            self._by_kind.setdefault(rule.kind, {})[rule.key_hash] = rule

    # --- identifiers --------------------------------------------------------------------
    def domain_hashes(self, domain: str) -> list[str]:
        """The domain and each parent with at least two labels (a.b.example → a.b.example, b.example)."""
        labels = domain.lower().rstrip(".").split(".")
        return [self.hasher("domain", ".".join(labels[i:])) for i in range(max(len(labels) - 1, 1))]

    def _rule(self, kind: str, key_hash: str) -> UserRule | None:
        return self._by_kind.get(kind, {}).get(key_hash)

    def rule(self, kind: str, key_hash: str | None) -> UserRule | None:
        """The active user rule for an already-hashed key (Sources index rows store only hashes)."""
        return self._rule(kind, key_hash) if key_hash else None

    # --- people -------------------------------------------------------------------------
    def person_reasons(self, addr: Address, *, chat_hash: str | None = None) -> list[Reason]:
        return self.hashed_person_reasons(
            self.hasher("person", addr.email.lower()), self.domain_hashes(addr.domain), chat_hash=chat_hash
        )

    def hashed_person_reasons(
        self, person_hash: str, domain_hashes: list[str], *, chat_hash: str | None = None
    ) -> list[Reason]:
        """As person_reasons, from stored hashes only (lineage re-checks in purge jobs)."""
        reasons: list[Reason] = []
        rule = self._rule("person", person_hash)
        if rule and not (chat_hash and chat_hash in rule.except_chats):
            reasons.append(Reason("user", "person", rule.id))
        return reasons + self.hashed_domain_reasons(domain_hashes, chat_hash=chat_hash)

    def domain_reasons(self, domain: str, *, chat_hash: str | None = None) -> list[Reason]:
        return self.hashed_domain_reasons(self.domain_hashes(domain), chat_hash=chat_hash)

    def hashed_domain_reasons(self, domains: list[str], *, chat_hash: str | None = None) -> list[Reason]:
        reasons: list[Reason] = []
        for dh in domains:
            rule = self._rule("domain", dh)
            if rule and not (chat_hash and chat_hash in rule.except_chats):
                reasons.append(Reason("user", "domain", rule.id))
            if dh in self.excluded_domains:
                reasons.append(Reason("tenant", "client_account", account_id=self.excluded_domains[dh]))
        if (
            self.external_mode == "approved_only"
            and not any(dh in self.org_domains for dh in domains)
            and not any(dh in self.approved_domains for dh in domains)
        ):
            reasons.append(Reason("tenant", "not_approved"))
        return reasons

    def people_reasons(self, people: Iterable[Address], *, chat_hash: str | None = None) -> list[Reason]:
        """Reasons from any participant other than the user. An address-less participant (a sender
        not on the chat roster) can't be checked, so it excludes."""
        out: list[Reason] = []
        for addr in people:
            if not addr.email:
                out.append(Reason("tenant", "unknown_participant"))
        return out + self._participants([a for a in people if a.email], chat_hash)

    def _participants(self, people: Iterable[Address], chat_hash: str | None = None) -> list[Reason]:
        out: list[Reason] = []
        me = (self.self_email or "").lower()
        for addr in people:
            if addr.email.lower() != me:
                out.extend(self.person_reasons(addr, chat_hash=chat_hash))
        return out

    # --- items ----------------------------------------------------------------------------
    def message(self, header: SentHeader) -> Decision:
        reasons: list[Reason] = []
        if rule := self._rule("thread", self.hasher("thread", header.conversation_id)):
            reasons.append(Reason("user", "thread", rule.id))
        reasons += self._participants(header.participants)
        return Decision(tuple(dict.fromkeys(reasons)))

    def chat(self, chat: Chat, *, meeting_hash: str | None = None, series_hash: str | None = None) -> Decision:
        """`meeting_hash`/`series_hash`: the calendar event a meeting chat belongs to, if known."""
        chat_hash = self.hasher("chat", chat.id)
        reasons: list[Reason] = []
        if rule := self._rule("chat", chat_hash):
            reasons.append(Reason("user", "chat", rule.id))
        reasons += self._meeting_reasons(meeting_hash, series_hash)
        if not chat.members_complete:
            reasons.append(Reason("tenant", "members_unknown"))
        reasons += self._participants(chat.members, chat_hash=chat_hash)
        return Decision(tuple(dict.fromkeys(reasons)))

    def _meeting_reasons(self, meeting_hash: str | None, series_hash: str | None) -> list[Reason]:
        reasons: list[Reason] = []
        if rule := self.rule("meeting", meeting_hash):
            reasons.append(Reason("user", "meeting", rule.id))
        if rule := self.rule("series", series_hash):
            reasons.append(Reason("user", "series", rule.id))
        return reasons

    def meeting(self, event: Event) -> Decision:
        reasons: list[Reason] = []
        if rule := self._rule("meeting", self.hasher("meeting", event.id)):
            reasons.append(Reason("user", "meeting", rule.id))
        if event.series_id and (rule := self._rule("series", self.hasher("series", event.series_id))):
            reasons.append(Reason("user", "series", rule.id))
        people = [*event.attendees, *([event.organizer] if event.organizer else [])]
        reasons += self._participants(people)
        return Decision(tuple(dict.fromkeys(reasons)))

    def lineage(
        self,
        people: Iterable[tuple[str, list[str]]],
        *,
        thread_hash: str | None = None,
        chat_hash: str | None = None,
        meeting_hash: str | None = None,
        series_hash: str | None = None,
    ) -> Decision:
        """Re-check a stored item from its lineage: (person hash, domain hashes) per participant
        other than the user, plus the thread or chat it came from (and a meeting chat's meeting)."""
        reasons: list[Reason] = []
        if rule := self.rule("thread", thread_hash):
            reasons.append(Reason("user", "thread", rule.id))
        if rule := self.rule("chat", chat_hash):
            reasons.append(Reason("user", "chat", rule.id))
        reasons += self._meeting_reasons(meeting_hash, series_hash)
        for person_hash, domains in people:
            reasons += self.hashed_person_reasons(person_hash, domains, chat_hash=chat_hash)
        return Decision(tuple(dict.fromkeys(reasons)))


def new_rule_id() -> str:
    return str(uuid.uuid4())
