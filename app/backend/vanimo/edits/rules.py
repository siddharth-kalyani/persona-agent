"""Learned style rules (architecture §9.2; research R05 §2.3 steps 4-6, §7.7).

Lifecycle: every style edit in a matched draft is an observation for a rule scoped to the
audience (relationship). A rule becomes **active** — used in drafts and shown to the user to
confirm — only when all of these hold (PROSE-style verification, deterministic in the MVP):

  * at least 3 observations from different drafts;
  * more than twice as many supporting as contradicting observations, and the latest one supports it;
  * the user's own sent messages to this audience agree with it (support), where there are enough.

The user then keeps it (**confirmed**, highest trust) or says "not me" (**rejected**: never used or
proposed again). Unconfirmed rules stop being used 90 days after their last observation.
Evidence is the edit event, which is deleted with its draft — so when a purge removes drafts,
their rules are re-counted and a rule with no evidence left is deleted (§6.5 X7).
"""

from __future__ import annotations

import json
import re
import statistics
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from vanimo.controls.neversend import Matcher
from vanimo.db.session import UserRef
from vanimo.edits.diff import Comparison, Edit
from vanimo.learning import style
from vanimo.learning.persona import load_items
from vanimo.redaction.marks import L1_MARKS, NEVER_SEND
from vanimo.redaction.pipeline import Hasher
from vanimo.vault import Vault

PROMOTE_AFTER = 3
DECAY_DAYS = 90
SERVE_MAX = 10
MIN_SUPPORT = {"greeting": 0.25, "sign_off": 0.25, "avoid": 0.9, "prefer": 0.5, "exclamations": 0.8, "length": 0.0}
RULE_KINDS = ("greeting", "sign_off", "length", "avoid", "prefer", "exclamations")


@dataclass(frozen=True)
class Rule:
    id: str
    scope: str
    kind: str
    value: str  # L1: a greeting or sign-off form, a phrase, "old -> new", "shorter", "none"
    status: str
    evidence: int
    contradictions: int
    support: float | None
    last_seen: datetime

    @property
    def text(self) -> str:
        return describe(self.kind, self.value)


def describe(kind: str, value: str) -> str:
    """The rule in plain words (for the user and for the prompt). Forms keep their placeholders."""
    if kind in ("greeting", "sign_off"):
        what = "greeting" if kind == "greeting" else "sign-off"
        return f"No {what}" if value == "(none)" else f'{what.capitalize()}: "{value}"'
    if kind == "length":
        return "Write shorter" if value == "shorter" else "Write longer"
    if kind == "avoid":
        return f'Don\'t write "{value}"'
    if kind == "prefer":
        old, _, new = value.partition(" -> ")
        return f'Write "{new}" instead of "{old}"'
    return "No exclamation marks"


def _contradicts(kind: str, value: str, edit: Edit) -> bool:
    if edit.kind != kind:
        return False
    if kind in ("greeting", "sign_off", "length"):
        return edit.value != value
    if kind == "prefer":
        old, _, new = value.partition(" -> ")
        return edit.value == f"{new} -> {old}"
    return False


def _usable(edit: Edit) -> bool:
    """Style edits only, and never a value holding a person, a slot or a never-send placeholder."""
    return (
        edit.kind in RULE_KINDS
        and 0 < len(edit.value) <= 80
        and not L1_MARKS.search(edit.value)
        and not re.search(r"\[[^\]]+\]", edit.value)
    )


async def record(
    conn: AsyncConnection,
    vault: Vault,
    ref: UserRef,
    hasher: Hasher,
    *,
    draft_id: str,
    source_kind: str,
    relationship: str,
    comparison: Comparison,
) -> str:
    """Store the edit event and its observations; re-count and verify the user's rules."""
    t, u = ref.tenant_id, ref.user_id
    event_id = str(
        (
            await conn.execute(
                text(
                    "insert into vanimo.edit_events (tenant_id, owner_user_id, draft_id, source_kind, outcome, "
                    "edit_share, draft_words, sent_words, relationship, edits) values (:t, :u, :d, :k, :o, :s, :dw, "
                    ":sw, :r, cast(:e as jsonb)) returning id"
                ),
                {
                    "t": t,
                    "u": u,
                    "d": draft_id,
                    "k": source_kind,
                    "o": comparison.outcome,
                    "s": comparison.edit_share,
                    "dw": comparison.draft_words,
                    "sw": comparison.sent_words,
                    "r": relationship,
                    # Content-free: the kinds of edit only.
                    "e": json.dumps(sorted({e.kind for e in comparison.edits})),
                },
            )
        ).scalar_one()
    )
    style_edits = [e for e in comparison.edits if _usable(e)]
    for edit in style_edits:
        key = hasher("rule", f"{source_kind}|{relationship}|{edit.kind}|{edit.value}")
        rule_id = (
            await conn.execute(
                text(
                    "insert into vanimo.style_rules (tenant_id, owner_user_id, source_kind, scope, kind, key_hash, "
                    "value_enc) values (:t, :u, :k, :s, :kind, :h, :v) on conflict (owner_user_id, source_kind, "
                    "key_hash) do update set last_seen = now() returning id"
                ),
                {
                    "t": t,
                    "u": u,
                    "k": source_kind,
                    "s": relationship,
                    "kind": edit.kind,
                    "h": key,
                    "v": vault.encrypt_user(t, u, edit.value, "style_rule"),
                },
            )
        ).scalar_one()
        await _evidence(conn, ref, rule_id, event_id, supports=True)
    # The same edit can also contradict rules already learned for this audience.
    existing = (
        await conn.execute(
            text(
                "select id, kind, value_enc from vanimo.style_rules where source_kind = :k and scope = :s "
                "and kind in ('greeting', 'sign_off', 'length', 'prefer')"
            ),
            {"k": source_kind, "s": relationship},
        )
    ).all()
    for r in existing:
        value = vault.decrypt_user(t, u, r.value_enc, "style_rule") or ""
        if any(_contradicts(r.kind, value, e) for e in comparison.edits):
            await _evidence(conn, ref, r.id, event_id, supports=False)
    await recount(conn, vault, ref, source_kind)
    return event_id


async def _evidence(conn: AsyncConnection, ref: UserRef, rule_id: Any, event_id: str, *, supports: bool) -> None:
    await conn.execute(
        text(
            "insert into vanimo.rule_evidence (tenant_id, owner_user_id, rule_id, edit_event_id, supports) "
            "values (:t, :u, :r, :e, :s) on conflict do nothing"
        ),
        {"t": ref.tenant_id, "u": ref.user_id, "r": rule_id, "e": event_id, "s": supports},
    )


def support(kind: str, value: str, items: list[str]) -> float | None:
    """How well the rule describes the user's own sent messages to this audience (None: too few)."""
    if kind == "length":
        return None  # the edits themselves are the evidence
    if len(items) < 3:
        return None
    if kind in ("greeting", "sign_off"):
        of = style.greeting_of if kind == "greeting" else style.sign_off_of
        want = None if value == "(none)" else value
        return round(sum(of(t) == want for t in items) / len(items), 2)
    if kind == "avoid":
        return round(1 - sum(value in " ".join(style._words(t)) for t in items) / len(items), 2)
    if kind == "prefer":
        old, _, new = value.partition(" -> ")
        words = [w for t in items for w in style._words(t)]
        n_old, n_new = words.count(old), words.count(new)
        return round(n_new / (n_old + n_new), 2) if n_old + n_new else None
    return round(1 - sum("!" in t for t in items) / len(items), 2)  # exclamations


async def recount(conn: AsyncConnection, vault: Vault, ref: UserRef, source_kind: str | None = None) -> None:
    """Re-count evidence for every rule; delete rules with none; promote and demote."""
    t, u = ref.tenant_id, ref.user_id
    await conn.execute(
        text(
            "update vanimo.style_rules r set evidence = coalesce(e.pos, 0), contradictions = coalesce(e.neg, 0) "
            "from (select r2.id, count(*) filter (where ev.supports) as pos, "
            "count(*) filter (where not ev.supports) as neg from vanimo.style_rules r2 "
            "left join vanimo.rule_evidence ev on ev.rule_id = r2.id group by r2.id) e where e.id = r.id"
        )
    )
    await conn.execute(text("delete from vanimo.style_rules where evidence = 0"))
    rows = (
        await conn.execute(
            text(
                "select r.id, r.source_kind, r.scope, r.kind, r.value_enc, r.status, r.evidence, r.contradictions, "
                "(select ev.supports from vanimo.rule_evidence ev "
                " join vanimo.edit_events ee on ee.id = ev.edit_event_id "
                " where ev.rule_id = r.id order by ee.created_at desc limit 1) as latest "
                "from vanimo.style_rules r where r.status in ('candidate', 'active') "
                "and (cast(:k as text) is null or r.source_kind = :k)"
            ),
            {"k": source_kind},
        )
    ).all()
    if not rows:
        return
    by_scope: dict[tuple[str, str], list[str]] = {}
    for kind in {r.source_kind for r in rows}:
        for item in await load_items(conn, vault, ref, kind):
            if item.channel == "email":
                by_scope.setdefault((kind, item.relationship), []).append(item.text)
    for r in rows:
        value = vault.decrypt_user(t, u, r.value_enc, "style_rule") or ""
        sup = support(r.kind, value, by_scope.get((r.source_kind, r.scope), []))
        ok = (
            r.evidence >= PROMOTE_AFTER
            and r.evidence > 2 * r.contradictions
            and r.latest is not False
            and (sup is None or sup >= MIN_SUPPORT[r.kind])
        )
        status = "active" if ok else "candidate"
        if status != r.status or sup is not None:
            await conn.execute(
                text("update vanimo.style_rules set status = :s, support = :p where id = :id"),
                {"s": status, "p": sup, "id": r.id},
            )


async def load_rules(
    conn: AsyncConnection,
    vault: Vault,
    ref: UserRef,
    source_kind: str,
    *,
    statuses: tuple[str, ...] = ("candidate", "active", "confirmed", "rejected"),
) -> list[Rule]:
    rows = (
        await conn.execute(
            text(
                "select id, scope, kind, value_enc, status, evidence, contradictions, support, last_seen "
                "from vanimo.style_rules where source_kind = :k and status = any(:st) "
                "order by (status = 'confirmed') desc, evidence desc, last_seen desc"
            ),
            {"k": source_kind, "st": list(statuses)},
        )
    ).all()
    return [
        Rule(
            id=str(r.id),
            scope=r.scope,
            kind=r.kind,
            value=vault.decrypt_user(ref.tenant_id, ref.user_id, r.value_enc, "style_rule") or "",
            status=r.status,
            evidence=r.evidence,
            contradictions=r.contradictions,
            support=r.support,
            last_seen=r.last_seen,
        )
        for r in rows
    ]


async def rules_for_draft(
    conn: AsyncConnection, vault: Vault, ref: UserRef, source_kind: str, relationship: str, matcher: Matcher
) -> list[Rule]:
    """Active and confirmed rules for this audience, freshest first. Unconfirmed rules decay after 90
    days without an observation; any rule touching a never-send word (added since) is left out."""
    cutoff = datetime.now(UTC) - timedelta(days=DECAY_DAYS)
    out = []
    for r in await load_rules(conn, vault, ref, source_kind, statuses=("active", "confirmed")):
        if r.scope not in (relationship, "*"):
            continue
        if r.status != "confirmed" and r.last_seen < cutoff:
            continue
        if matcher.count(r.value) or NEVER_SEND.search(r.value):
            continue
        out.append(r)
    return out[:SERVE_MAX]


async def scrub(conn: AsyncConnection, vault: Vault, ref: UserRef, matcher: Matcher) -> int:
    """A never-send word added: rules whose value holds it are deleted (with their evidence)."""
    if not matcher:
        return 0
    doomed = [
        r.id
        for r in await load_rules(conn, vault, ref, "graph") + await load_rules(conn, vault, ref, "sample")
        if matcher.count(r.value)
    ]
    if doomed:
        await conn.execute(text("delete from vanimo.style_rules where id = any(cast(:ids as uuid[]))"), {"ids": doomed})
    return len(doomed)


def summarise(outcomes: list[tuple[str, float, str]]) -> dict[str, Any]:
    """MESR and friends from (outcome, edit share, relationship) of matched drafts."""
    n = len(outcomes)
    if not n:
        return {"matched": 0}
    count = {k: sum(o == k for o, _, _ in outcomes) for k in ("sent_as_is", "light_edit", "heavy_edit", "rewritten")}
    by_rel: dict[str, list[str]] = {}
    for o, _, rel in outcomes:
        by_rel.setdefault(rel, []).append(o)
    return {
        "matched": n,
        **count,
        "sendWithoutEditRate": round(count["sent_as_is"] / n, 3),
        "lightEditRate": round((count["sent_as_is"] + count["light_edit"]) / n, 3),
        "medianEditShare": round(statistics.median(s for _, s, _ in outcomes), 3),
        "byRelationship": {
            rel: {"matched": len(os), "sendWithoutEditRate": round(os.count("sent_as_is") / len(os), 3)}
            for rel, os in sorted(by_rel.items())
        },
    }
