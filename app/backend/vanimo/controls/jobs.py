"""Purge and scrub jobs, with receipts (architecture §6.5 X7, docs/research/12 §9.5).

Logical exclusion is immediate: the engine reads rules live, so a new rule applies to the very
next fetch, retrieval or draft. These jobs do the physical work and leave a receipt:

* exclusion added   — delete everything derived from the excluded sources. In M1 nothing is
                      derived yet (no bodies, style cards or memory exist before M2), so the job
                      records zero deletions; M2 registers its stores here.
* never-send added  — re-mask every display field already stored (the Sources index now; L1
                      text, vectors and memory from M2) so the new word disappears from history.
* removals          — rules and words are revoked going forward; history is not restored.

The target is ≤ 24 h; locally they finish in seconds.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from vanimo.controls.store import load_matcher
from vanimo.db.session import UserRef, user_tx
from vanimo.logs import get_logger
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


async def run_job(engine: AsyncEngine, vault: Vault, ref: UserRef, job_id: str, reason: str) -> None:
    async with user_tx(engine, ref) as conn:
        await conn.execute(text("update vanimo.purge_jobs set status = 'running' where id = :id"), {"id": job_id})
    try:
        counts: dict[str, Any] = {}
        if reason == "term_added":
            counts["index_fields_rescrubbed"] = await scrub_index(engine, vault, ref)
        elif reason == "exclusion_added":
            # Nothing is derived from message content before M2; stores register here as they arrive.
            counts["derived_items_deleted"] = 0
        status = "done"
    except Exception as exc:
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
