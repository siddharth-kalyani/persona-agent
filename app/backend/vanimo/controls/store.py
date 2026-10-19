"""Database access for data controls. Every function takes a connection opened with `user_tx`,
so row-level security limits it to the caller's own rows (and their tenant's policy rows)."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from vanimo.controls.engine import ExclusionEngine, UserRule
from vanimo.controls.neversend import Matcher, Term
from vanimo.db.session import UserRef
from vanimo.vault import Vault, normalise_identifier


def hasher_for(vault: Vault, ref: UserRef):  # type: ignore[no-untyped-def]
    def _hash(kind: str, value: str) -> str:
        return vault.key_hash(ref.tenant_id, kind, normalise_identifier(kind, value))

    return _hash


async def load_terms(conn: AsyncConnection, vault: Vault, ref: UserRef) -> list[dict[str, Any]]:
    rows = (
        await conn.execute(
            text(
                "select id, term_id, term_enc, variants_enc, kind, allow_in_drafts, folds, created_at "
                "from vanimo.never_send_terms order by created_at"
            )
        )
    ).all()
    out = []
    for r in rows:
        variants = vault.decrypt_user(ref.tenant_id, ref.user_id, r.variants_enc, "ns_variants")
        out.append(
            {
                "id": str(r.id),
                "term_id": r.term_id,
                "text": vault.decrypt_user(ref.tenant_id, ref.user_id, r.term_enc, "ns_term"),
                "variants": json.loads(variants) if variants else [],
                "kind": r.kind,
                "allow_in_drafts": r.allow_in_drafts,
                "folds": r.folds,
                "created_at": r.created_at,
            }
        )
    return out


async def load_matcher(conn: AsyncConnection, vault: Vault, ref: UserRef) -> Matcher:
    """The user's never-send matcher. Decrypted terms live only inside the returned object."""
    terms = await load_terms(conn, vault, ref)
    return Matcher([Term(t["term_id"], t["text"], t["kind"], tuple(t["variants"]), t["folds"]) for t in terms])


async def lock_user_controls(conn: AsyncConnection, ref: UserRef) -> None:
    """Serialise index writes (scan replace, never-send scrub) per user until the transaction ends,
    so a word added during a scan can never be overwritten by unmasked text."""
    await conn.execute(text("select pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"controls:{ref.user_id}"})


async def load_engine(
    conn: AsyncConnection,
    vault: Vault,
    ref: UserRef,
    *,
    self_email: str | None = None,
    extra_org_domains: Iterable[str] = (),
) -> ExclusionEngine:
    """`extra_org_domains`: domains to treat as the organisation's own for this evaluation only.
    The sample workspace passes its fictional company's domain, so in a real tenant using
    "approved clients only" the sample colleagues aren't treated as unapproved externals (the
    sample domain is never recorded in a real tenant's table)."""
    rules = (
        await conn.execute(text("select id, kind, key_hash from vanimo.exclusion_rules where status = 'active'"))
    ).all()
    exceptions: dict[str, set[str]] = {}
    for r in (await conn.execute(text("select rule_id, chat_hash from vanimo.exclusion_exceptions"))).all():
        exceptions.setdefault(str(r.rule_id), set()).add(r.chat_hash)
    accounts = (
        await conn.execute(
            text(
                "select d.domain_hash, a.id, a.mode from vanimo.client_account_domains d "
                "join vanimo.client_accounts a on a.id = d.account_id"
            )
        )
    ).all()
    mode = (await conn.execute(text("select external_mode from vanimo.tenant_policies"))).scalar_one_or_none()
    # The organisation's own domains, known tenant-wide (not from one user's latest scan).
    org_domains = (await conn.execute(text("select domain_hash from vanimo.tenant_org_domains"))).scalars().all()
    return ExclusionEngine(
        hasher=hasher_for(vault, ref),
        user_rules=[UserRule(str(r.id), r.kind, r.key_hash, frozenset(exceptions.get(str(r.id), ()))) for r in rules],
        excluded_domains={a.domain_hash: str(a.id) for a in accounts if a.mode == "excluded"},
        approved_domains=frozenset(a.domain_hash for a in accounts if a.mode == "approved"),
        external_mode=mode or "allow_all",
        org_domains=frozenset(org_domains)
        | frozenset(
            vault.key_hash(ref.tenant_id, "domain", normalise_identifier("domain", d)) for d in extra_org_domains
        ),
        self_email=self_email,
    )


async def bump_version(conn: AsyncConnection, ref: UserRef) -> int:
    """Per-user controls epoch: content pipelines re-check it so a rule added mid-flight wins."""
    return (
        await conn.execute(
            text(
                "insert into vanimo.controls_state (owner_user_id, tenant_id, version) values (:u, :t, 1) "
                "on conflict (owner_user_id) do update set version = vanimo.controls_state.version + 1, "
                "updated_at = now() returning version"
            ),
            {"u": ref.user_id, "t": ref.tenant_id},
        )
    ).scalar_one()


async def add_purge_job(conn: AsyncConnection, ref: UserRef, reason: str) -> str:
    return str(
        (
            await conn.execute(
                text(
                    "insert into vanimo.purge_jobs (tenant_id, owner_user_id, reason) values (:t, :u, :r) returning id"
                ),
                {"t": ref.tenant_id, "u": ref.user_id, "r": reason},
            )
        ).scalar_one()
    )
