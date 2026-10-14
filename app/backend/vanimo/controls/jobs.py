"""Purge and scrub jobs, with receipts (architecture §6.5 X7, docs/research/12 §9.5).

Logical exclusion is immediate: the engine reads rules live, so a new rule applies to the very
next fetch, retrieval or draft. These jobs do the physical work and leave a receipt:

* exclusion added   — delete everything derived from the excluded sources: L1 items and drafts
                      whose lineage (thread/chat, participants, their domains) the engine now
                      excludes (with their edit events and rule evidence; rules left without
                      evidence go too), tokens no remaining item uses, and style cards (rebuilt
                      from what's left).
* never-send added  — re-mask every display field already stored: the Sources index, L1 text,
                      contexts and subjects (and their vectors), drafts, token values, studio
                      phrases; learned rules holding the word are deleted; style cards are
                      rebuilt so no phrase keeps the word.
* learning deleted  — the user's "delete what you learned": every L1 item, token, style card,
                      evaluation, draft, edit event and learned rule is removed (studio settings
                      and drafting settings are the user's own and are kept).
* removals          — rules and words are revoked going forward; history is not restored.

The target is ≤ 24 h; locally they finish in seconds.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from vanimo.controls.store import bump_version, load_engine, load_matcher, lock_user_controls
from vanimo.db.session import UserRef, user_tx
from vanimo.edits import rules
from vanimo.learning.embed import embed
from vanimo.learning.persona import PersonaSettings, mask_settings, rebuild
from vanimo.logs import get_logger
from vanimo.redaction.marks import L1_MARKS, TOKEN
from vanimo.sources.sample import ORG_DOMAIN as SAMPLE_DOMAIN
from vanimo.vault import Vault

log = get_logger("vanimo.jobs")

# Encrypted display fields in the Sources index that can contain never-send words.
SCRUB_FIELDS = {
    "source_people": [("name_enc", "name")],
    "source_threads": [("subject_enc", "subject")],
    "source_chats": [("topic_enc", "topic"), ("label_enc", "chat_label")],
    "source_meetings": [("subject_enc", "subject")],
}


async def scrub_index(engine: AsyncEngine, vault: Vault, ref: UserRef) -> int:
    """Re-mask the Sources index with the user's current never-send words. Returns fields changed."""
    t, u = ref.tenant_id, ref.user_id
    changed = 0
    async with user_tx(engine, ref) as conn:
        await lock_user_controls(conn, ref)  # never interleave with a scan replacing the index
        matcher = await load_matcher(conn, vault, ref)
        if not matcher:
            return 0
        for table, fields in SCRUB_FIELDS.items():
            cols = ", ".join(c for c, _ in fields)
            rows = (await conn.execute(text(f"select id, {cols} from vanimo.{table}"))).all()  # noqa: S608
            for row in rows:
                updates: dict[str, Any] = {}
                for col, purpose in fields:
                    plain = vault.decrypt_user(t, u, getattr(row, col), purpose)
                    masked, hits = matcher.mask(plain)
                    if hits:
                        updates[col] = vault.encrypt_user(t, u, masked, purpose)
                if updates:
                    sets = ", ".join(f"{c} = :{c}" for c in updates)
                    await conn.execute(
                        text(f"update vanimo.{table} set {sets} where id = :id"),  # noqa: S608
                        {**updates, "id": row.id},
                    )
                    changed += len(updates)
    return changed


SAMPLE_ORG_DOMAINS = frozenset({SAMPLE_DOMAIN})
L1_FIELDS = [("subject_enc", "l1_subject"), ("text_enc", "l1_text"), ("context_enc", "l1_context")]


async def scrub_learning(engine: AsyncEngine, vault: Vault, ref: UserRef, rebuild_sources: list[str]) -> dict[str, int]:
    """Re-mask learned text with the user's current never-send words (and re-derive vectors)."""
    t, u = ref.tenant_id, ref.user_id
    changed_items = changed_tokens = 0
    async with user_tx(engine, ref) as conn:
        await lock_user_controls(conn, ref)
        matcher = await load_matcher(conn, vault, ref)
        if not matcher:
            return {}
        rows = (
            await conn.execute(text("select id, source_kind, subject_enc, text_enc, context_enc from vanimo.l1_items"))
        ).all()
        for row in rows:
            masked = {
                col: matcher.mask(vault.decrypt_user(t, u, getattr(row, col), purpose), opaque=L1_MARKS)
                for col, purpose in L1_FIELDS
            }
            if not any(hits for _, hits in masked.values()):
                continue
            subject, body, context = (masked[col][0] for col, _ in L1_FIELDS)
            await conn.execute(
                text(
                    "update vanimo.l1_items set subject_enc = :s, text_enc = :x, context_enc = :c, "
                    "vec = cast(:v as real[]) where id = :id"
                ),
                {
                    "s": vault.encrypt_user(t, u, subject, "l1_subject"),
                    "x": vault.encrypt_user(t, u, body, "l1_text"),
                    "c": vault.encrypt_user(t, u, context, "l1_context"),
                    "v": embed(f"{subject or ''}\n{context or ''}"),
                    "id": row.id,
                },
            )
            changed_items += 1
            if row.source_kind not in rebuild_sources:
                rebuild_sources.append(row.source_kind)
        for row in (await conn.execute(text("select token, value_enc from vanimo.l1_tokens"))).all():
            value, hits = matcher.mask(vault.decrypt_user(t, u, row.value_enc, "l1_token"))
            if hits:
                await conn.execute(
                    text("update vanimo.l1_tokens set value_enc = :v where token = :tok"),
                    {"v": vault.encrypt_user(t, u, value, "l1_token"), "tok": row.token},
                )
                changed_tokens += 1
        changed_drafts = 0
        for row in (await conn.execute(text("select id, text_enc from vanimo.drafts"))).all():
            masked, hits = matcher.mask(vault.decrypt_user(t, u, row.text_enc, "draft_text"), opaque=L1_MARKS)
            if hits:
                await conn.execute(
                    text("update vanimo.drafts set text_enc = :x where id = :id"),
                    {"x": vault.encrypt_user(t, u, masked, "draft_text"), "id": row.id},
                )
                changed_drafts += 1
        rules_deleted = await rules.scrub(conn, vault, ref, matcher)
        enc = (await conn.execute(text("select settings_enc from vanimo.persona_settings"))).scalar_one_or_none()
        if enc:
            current = PersonaSettings.model_validate_json(vault.decrypt_user(t, u, enc, "persona") or "{}")
            masked_settings = mask_settings(current, matcher)
            if masked_settings != current:
                await conn.execute(
                    text("update vanimo.persona_settings set settings_enc = :s, updated_at = now()"),
                    {"s": vault.encrypt_user(t, u, masked_settings.model_dump_json(), "persona")},
                )
    return {
        "l1_items_rescrubbed": changed_items,
        "tokens_rescrubbed": changed_tokens,
        "drafts_rescrubbed": changed_drafts,
        "rules_deleted": rules_deleted,
    }


async def purge_excluded_learning(
    engine: AsyncEngine, vault: Vault, ref: UserRef, rebuild_sources: list[str]
) -> dict[str, int]:
    """Delete learned items the current rules exclude, judged from their stored lineage."""
    async with user_tx(engine, ref) as conn:
        await lock_user_controls(conn, ref)
        ex_engine = await load_engine(conn, vault, ref)
        # Sample items are judged with the sample company's own domain as internal (as when learned).
        sample_engine = await load_engine(conn, vault, ref, extra_org_domains=SAMPLE_ORG_DOMAINS)
        rows = (
            await conn.execute(
                text(
                    "select id, source_kind, channel, thread_hash, meeting_hash, series_hash, people "
                    "from vanimo.l1_items"
                )
            )
        ).all()
        doomed = []
        for r in rows:
            people = [(p["p"], list(p["d"])) for p in r.people]
            on_thread = r.thread_hash if r.channel == "email" else None
            on_chat = r.thread_hash if r.channel == "chat" else None
            decision = (sample_engine if r.source_kind == "sample" else ex_engine).lineage(
                people,
                thread_hash=on_thread,
                chat_hash=on_chat,
                meeting_hash=r.meeting_hash,
                series_hash=r.series_hash,
            )
            if decision.excluded:
                doomed.append(r.id)
                if r.source_kind not in rebuild_sources:
                    rebuild_sources.append(r.source_kind)
        if doomed:
            await conn.execute(text("delete from vanimo.l1_items where id = any(:ids)"), {"ids": doomed})
        tokens_deleted = await gc_tokens(conn, vault, ref) if doomed else 0
        drafts = (await conn.execute(text("select id, source_kind, thread_hash, people from vanimo.drafts"))).all()
        doomed_drafts = [
            d.id
            for d in drafts
            if (sample_engine if d.source_kind == "sample" else ex_engine)
            .lineage([(p["p"], list(p["d"])) for p in d.people], thread_hash=d.thread_hash)
            .excluded
        ]
        rules_before = (await conn.execute(text("select count(*) from vanimo.style_rules"))).scalar_one()
        if doomed_drafts:
            # Their edit events and rule evidence go with them (foreign keys); rules are re-counted.
            await conn.execute(text("delete from vanimo.drafts where id = any(:ids)"), {"ids": doomed_drafts})
        if doomed_drafts or doomed:
            await rules.recount(conn, vault, ref)
        rules_after = (await conn.execute(text("select count(*) from vanimo.style_rules"))).scalar_one()
    return {
        "l1_items_deleted": len(doomed),
        "tokens_deleted": tokens_deleted,
        "drafts_deleted": len(doomed_drafts),
        "rules_deleted": rules_before - rules_after,
    }


async def gc_tokens(conn: AsyncConnection, vault: Vault, ref: UserRef) -> int:
    """Tokens no remaining item mentions are deleted (their values are names and addresses)."""
    t, u = ref.tenant_id, ref.user_id
    used: set[str] = set()
    for row in (await conn.execute(text("select subject_enc, text_enc, context_enc from vanimo.l1_items"))).all():
        for col, purpose in L1_FIELDS:
            used |= set(TOKEN.findall(vault.decrypt_user(t, u, getattr(row, col), purpose) or ""))
    stored = (await conn.execute(text("select token from vanimo.l1_tokens"))).scalars().all()
    unused = [tok for tok in stored if tok not in used]
    if unused:
        await conn.execute(text("delete from vanimo.l1_tokens where token = any(:t)"), {"t": unused})
    return len(unused)


async def delete_learning(engine: AsyncEngine, ref: UserRef) -> dict[str, int]:
    out: dict[str, int] = {}
    async with user_tx(engine, ref) as conn:
        await lock_user_controls(conn, ref)
        # A run still collecting must not store its items after this: it is cancelled here, and
        # its persist step checks the run is still running (under the same lock).
        cancelled = await conn.execute(
            text(
                "update vanimo.learning_runs set status = 'failed', finished_at = now(), error_code = 'cancelled' "
                "where status = 'running'"
            )
        )
        out["learning_runs_cancelled"] = cancelled.rowcount
        await bump_version(conn, ref)
        for table in ("l1_items", "l1_tokens", "style_cards", "eval_runs", "drafts", "style_rules"):
            result = await conn.execute(text(f"delete from vanimo.{table}"))  # noqa: S608
            out[f"{table}_deleted"] = result.rowcount
    return out


async def run_job(engine: AsyncEngine, vault: Vault, ref: UserRef, job_id: str, reason: str) -> None:
    async with user_tx(engine, ref) as conn:
        await conn.execute(
            text(
                "update vanimo.purge_jobs set status = 'running', lease_until = now() + interval '10 minutes' "
                "where id = :id"
            ),
            {"id": job_id},
        )
    try:
        counts: dict[str, Any] = {}
        rebuild_sources: list[str] = []
        if reason == "term_added":
            counts["index_fields_rescrubbed"] = await scrub_index(engine, vault, ref)
            counts |= await scrub_learning(engine, vault, ref, rebuild_sources)
        elif reason in ("exclusion_added", "tenant_policy_changed"):
            counts |= await purge_excluded_learning(engine, vault, ref, rebuild_sources)
        elif reason == "learning_deleted":
            counts |= await delete_learning(engine, ref)
        if reason in ("term_added", "exclusion_added", "tenant_policy_changed"):
            # Every source with learned data, not only the ones this attempt changed: a retry
            # after a failed rebuild finds nothing left to delete but must still rebuild the cards.
            async with user_tx(engine, ref) as conn:
                kinds = set(rebuild_sources) | set(
                    (
                        await conn.execute(
                            text(
                                "select source_kind from vanimo.l1_items "
                                "union select source_kind from vanimo.style_cards"
                            )
                        )
                    ).scalars()
                )
            for kind in sorted(kinds):
                counts["style_cards_rebuilt"] = counts.get("style_cards_rebuilt", 0) + await rebuild(
                    engine, vault, ref, kind
                )
        status = "done"
    except Exception as exc:
        # The sweeper retries up to 3 times; after that the receipt shows "needs attention" and the
        # user (or an operator alerted on this event) can retry it.
        log.error("jobs.failed", error_type=type(exc).__name__)
        counts, status = {"error_type": type(exc).__name__}, "failed"
    async with user_tx(engine, ref) as conn:
        await conn.execute(
            text(
                "update vanimo.purge_jobs set status = :s, completed_at = now(), counts = cast(:c as jsonb) "
                "where id = :id"
            ),
            {"s": status, "c": json.dumps(counts), "id": job_id},
        )
    log.info("jobs.done", outcome=status)
