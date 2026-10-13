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
covers every chat the person is in, except chats the user explicitly unticked (D5).
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
    user_rules: list[UserRule] = field(default_factory=list)
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
        reasons: list[Reason] = []
        rule = self._rule("person", self.hasher("person", addr.email.lower()))
        if rule and not (chat_hash and chat_hash in rule.except_chats):
            reasons.append(Reason("user", "person", rule.id))
        return reasons + self.domain_reasons(addr.domain)

    def domain_reasons(self, domain: str) -> list[Reason]:
        reasons: list[Reason] = []
        domains = self.domain_hashes(domain)
        for dh in domains:
            if rule := self._rule("domain", dh):
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
        reasons += self._participants(header.recipients)
        return Decision(tuple(dict.fromkeys(reasons)))

    def chat(self, chat: Chat) -> Decision:
        chat_hash = self.hasher("chat", chat.id)
        reasons: list[Reason] = []
        if rule := self._rule("chat", chat_hash):
            reasons.append(Reason("user", "chat", rule.id))
        reasons += self._participants(chat.members, chat_hash=chat_hash)
        return Decision(tuple(dict.fromkeys(reasons)))

    def meeting(self, event: Event) -> Decision:
        reasons: list[Reason] = []
        if rule := self._rule("meeting", self.hasher("meeting", event.id)):
            reasons.append(Reason("user", "meeting", rule.id))
        if event.series_id and (rule := self._rule("series", self.hasher("series", event.series_id))):
            reasons.append(Reason("user", "series", rule.id))
        people = [*event.attendees, *([event.organizer] if event.organizer else [])]
        reasons += self._participants(people)
        return Decision(tuple(dict.fromkeys(reasons)))


def new_rule_id() -> str:
    return str(uuid.uuid4())
