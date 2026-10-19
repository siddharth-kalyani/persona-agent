"""L1 snapshots for Amazon Macie (architecture §7.2 S13, F11).

Production keeps L1 in S3 and Macie scans those buckets. The MVP keeps L1 encrypted in Postgres, so a
snapshot of each user's L1 text is written to a dedicated bucket for the scheduled Macie job to scan:

* one object per user, `l1/<tenant id>/<user id>.jsonl`, rewritten every `snapshot_every_hours` and
  whenever L1 was deleted or changed (database triggers count changes; the next sweep, within minutes,
  rewrites it). A purge job deletes it at once. An unchanged snapshot isn't uploaded again, so Macie
  (which re-reads only new or changed objects) doesn't report the same thing every day. The bucket's
  lifecycle rule removes any object not refreshed within 3 days;
* each line is `{"t": table, "f": field, "text": L1}`: no row ID or any other number of ours, so
  nothing Vanimo writes can look like an Aadhaar number (the manifest below names each line's row). Only
  L1 text: never the token → value map (`l1_tokens`), names from the Sources index, or never-send terms;
* the export keeps a manifest (table + row ID per line) and the object's ETag, so a finding's line
  numbers name the exact rows (an admin can remove them without seeing them);
* SSE-S3, TLS only, no public access; only Macie may read objects (bucket policy, `app/infra`).

Offline (`macie=offline`), nothing leaves the database: the same snapshot is scanned in process by
our own detectors and a hit is recorded exactly as a Macie finding would be.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from vanimo.backstops import Backstops
from vanimo.controls.jobs import COMMITMENT_FIELDS, L1_FIELDS, MEMORY_FIELDS
from vanimo.controls.store import lock_user_controls
from vanimo.db.session import UserRef, user_tx
from vanimo.logs import get_logger
from vanimo.redaction import detectors
from vanimo.redaction.marks import L1_MARKS
from vanimo.vault import Vault

log = get_logger("vanimo.backstops")

# Every table holding L1 text, with its encrypted fields and their vault purposes.
SNAPSHOT_FIELDS: dict[str, list[tuple[str, str]]] = {
    "l1_items": L1_FIELDS,
    "commitments": COMMITMENT_FIELDS,
    **MEMORY_FIELDS,
    "drafts": [("text_enc", "draft_text")],
    "style_cards": [("card_enc", "style_card")],
    "style_rules": [("value_enc", "style_rule")],
}
# Far beyond an MVP user's L1. Checked while building, so an oversized user can't exhaust memory.
MAX_SNAPSHOT_BYTES = 50 * 1024 * 1024
EXPORT_BATCH = 50


def key_for(ref: UserRef) -> str:
    return f"l1/{ref.tenant_id}/{ref.user_id}.jsonl"


class S3SnapshotStore:
    def __init__(self, bucket: str, region: str, *, client: Any = None) -> None:
        if client is None:
            import boto3
            from botocore.config import Config

            client = boto3.client(
                "s3",
                region_name=region,
                config=Config(retries={"mode": "standard", "max_attempts": 4}, connect_timeout=5, read_timeout=60),
            )
        self._client = client
        self.bucket = bucket

    async def put(self, key: str, body: bytes) -> str:
        """Writes the object; returns its ETag (Macie reports it with each finding)."""
        resp = await asyncio.to_thread(
            self._client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType="application/x-ndjson",
            ServerSideEncryption="AES256",
        )
        return clean_etag(resp.get("ETag"))

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._client.delete_object, Bucket=self.bucket, Key=key)


def clean_etag(etag: Any) -> str:
    return str(etag or "").strip('"')[:80]


@dataclass(frozen=True)
class Exported:
    items: int
    bytes: int
    stored: bool
    offline_findings: int | None = None
    uploaded: bool = False


async def build(conn: AsyncConnection, vault: Vault, ref: UserRef) -> tuple[list[dict[str, str]], list[str]]:
    """(snapshot lines, the row ID of each line)."""
    t, u = ref.tenant_id, ref.user_id
    lines: list[dict[str, str]] = []
    ids: list[str] = []
    size = 0
    for table, fields in SNAPSHOT_FIELDS.items():
        cols = ", ".join(c for c, _ in fields)
        rows = (await conn.execute(text(f"select id, {cols} from vanimo.{table} order by id"))).all()  # noqa: S608
        for row in rows:
            for col, purpose in fields:
                value = vault.decrypt_user(t, u, getattr(row, col), purpose)
                if value:
                    # The row ID goes to the manifest, never into the object: our own numbers (a UUID's digit
                    # groups) must not look like an Aadhaar number to Macie.
                    lines.append({"t": table, "f": col.removesuffix("_enc"), "text": value})
                    ids.append(str(row.id))
                    size += len(value) * 4 + 100  # worst case UTF-8 plus the line's own fields
                    if size > MAX_SNAPSHOT_BYTES:
                        # Refuse rather than write part of it: Macie would never see the rest.
                        raise ValueError("snapshot too large")
    return lines, ids


def offline_scan(lines: list[dict[str, str]]) -> tuple[dict[str, int], list[int]]:
    """The stand-in for Macie: identifiers our own detectors find in any value of a line, as Macie reads
    each JSON value (Vanimo's marks don't count). Returns (types → counts, line numbers with a hit)."""
    found: Counter[str] = Counter()
    hit: list[int] = []
    for i, line in enumerate(lines):
        kinds = [s.kind for value in line.values() for s in detectors.detect(L1_MARKS.sub(" ", value))]
        if kinds:
            found.update(kinds)
            hit.append(i)
    return dict(found), hit


async def record_finding(
    engine: AsyncEngine,
    ref: UserRef,
    finding_id: str,
    kinds: dict[str, int],
    severity: str | None,
    *,
    etag: str | None = None,
    records: list[int] | None = None,
) -> bool:
    """A finding against a user's snapshot: recorded once (by its ID), its line numbers turned into rows
    through the manifest of the snapshot with this ETag, and the tenant paused."""
    from vanimo.backstops.events import clean_kinds

    async with engine.begin() as conn:
        new = (
            await conn.execute(
                text(
                    "select vanimo_private.record_backstop_finding(:t, :u, 'macie', :f, cast(:k as jsonb), :s, :e, "
                    "cast(:r as jsonb))"
                ),
                {
                    "t": ref.tenant_id,
                    "u": ref.user_id,
                    "f": finding_id,
                    "k": json.dumps(clean_kinds(kinds) or {"unspecified": 1}),
                    "s": severity,
                    "e": etag or None,
                    "r": json.dumps(sorted(set(records or []))[:200]),
                },
            )
        ).scalar_one()
    if new:
        log.warning("backstops.tenant_paused", source="macie", count=sum(kinds.values()))
    return bool(new)


async def export_user(engine: AsyncEngine, vault: Vault, backstops: Backstops, ref: UserRef) -> Exported:
    """Reads, writes and books the snapshot under the user's controls lock, as purge jobs do, so a purge
    never finishes between reading the L1 and writing it. The change count is read before the data: a
    deletion committed meanwhile leaves the snapshot due for the next sweep."""
    async with user_tx(engine, ref) as conn:  # the row exists first, so the triggers can count changes
        await conn.execute(
            text(
                "insert into vanimo.l1_snapshots (owner_user_id, tenant_id, exported_at) values (:u, :t, 'epoch') "
                "on conflict (owner_user_id) do nothing"
            ),
            {"u": ref.user_id, "t": ref.tenant_id},
        )
    async with user_tx(engine, ref) as conn:
        await lock_user_controls(conn, ref)
        prev = (await conn.execute(text("select changes, content_hash, stored, etag from vanimo.l1_snapshots"))).one()
        lines, ids = await build(conn, vault, ref)
        body = "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines).encode()
        digest = hashlib.sha256(body).hexdigest()
        stored, uploaded, etag = False, False, None
        kinds: dict[str, int] = {}
        hit: list[int] = []
        if backstops.macie_mode == "aws":
            if not lines:
                await backstops.snapshot_store.delete(key_for(ref))
            elif prev.stored and prev.content_hash == digest and prev.etag:
                stored, etag = True, prev.etag  # unchanged: Macie has seen it, nothing to upload
            else:
                etag = await backstops.snapshot_store.put(key_for(ref), body)
                stored = uploaded = True
        else:
            kinds, hit = offline_scan(lines)
            etag = digest[:32]  # the offline "object" is identified by its content
        findings = None if backstops.macie_mode == "aws" else sum(kinds.values())
        await conn.execute(
            text(
                "update vanimo.l1_snapshots set exported_at = now(), exported_changes = :c, items = :n, bytes = :b, "
                "stored = :s, content_hash = :h, etag = :e, manifest = cast(:m as jsonb), offline_findings = :f"
            ),
            {
                "c": prev.changes,
                "n": len(lines),
                "b": len(body),
                "s": stored,
                "h": digest if lines else None,
                "e": etag,
                "m": json.dumps([[x["t"], rid] for x, rid in zip(lines, ids, strict=True)]),
                "f": findings,
            },
        )
    if kinds:
        await record_finding(engine, ref, f"offline:{ref.user_id}:{digest[:24]}", kinds, "high", etag=etag, records=hit)
    return Exported(len(lines), len(body), stored, findings, uploaded)


async def forget(engine: AsyncEngine, backstops: Backstops, ref: UserRef) -> None:
    """After a purge job: the snapshot goes now, not at the next export. If S3 can't be reached, the
    snapshot is left due (stored, with a change counted), so the next sweep rewrites or deletes it."""
    async with user_tx(engine, ref) as conn:
        await lock_user_controls(conn, ref)
        if backstops.macie_mode == "aws":
            try:
                await backstops.snapshot_store.delete(key_for(ref))
            except Exception as exc:
                log.warning("backstops.snapshot_delete_failed", error_type=type(exc).__name__)
                await conn.execute(
                    text(
                        "insert into vanimo.l1_snapshots (owner_user_id, tenant_id, exported_at, stored, changes) "
                        "values (:u, :t, 'epoch', true, 1) on conflict (owner_user_id) do update "
                        "set stored = true, changes = vanimo.l1_snapshots.changes + 1, content_hash = null"
                    ),
                    {"u": ref.user_id, "t": ref.tenant_id},
                )
                return
        await conn.execute(text("delete from vanimo.l1_snapshots"))


async def export_due(
    engine: AsyncEngine, vault: Vault, backstops: Backstops, *, admin: UserRef | None = None, limit: int = EXPORT_BATCH
) -> dict[str, int]:
    """Exports the snapshots that are due (sweeper), or every user's in the admin's tenant now."""
    if admin is not None:
        async with user_tx(engine, admin, admin=True) as conn:
            due = (
                await conn.execute(
                    text("select * from vanimo_private.snapshot_due(:h, :n, :t)"),
                    {"h": backstops.snapshot_every_hours, "n": 500, "t": admin.tenant_id},
                )
            ).all()
    else:
        async with engine.begin() as conn:
            due = (
                await conn.execute(
                    text("select * from vanimo_private.snapshot_due(:h, :n, null)"),
                    {"h": backstops.snapshot_every_hours, "n": limit},
                )
            ).all()
    out = {"exported": 0, "failed": 0, "findings": 0}
    for row in due:
        try:
            done = await export_user(engine, vault, backstops, UserRef(row.tenant_id, row.user_id))
        except Exception as exc:  # the next round retries; one user never blocks the others
            log.warning("backstops.snapshot_failed", error_type=type(exc).__name__)
            out["failed"] += 1
            continue
        out["exported"] += 1
        out["findings"] += done.offline_findings or 0
    if out["exported"] or out["failed"]:
        log.info("backstops.snapshots", count=out["exported"], outcome=f"failed_{out['failed']}")
    return out
