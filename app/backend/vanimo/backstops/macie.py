"""Amazon Macie findings → paused tenants (architecture §7.2 S13 "Findings ⇒ pause tenant pipeline").

A scheduled Macie job (created by `python -m vanimo.ops.macie_job`) scans the L1 snapshot bucket daily
with Macie's managed identifiers plus Vanimo's custom ones for Indian identifiers (`app/infra`). Each
later run reads only objects written since the one before, and every snapshot is rewritten daily.

The sweeper polls findings for the bucket (`poll_round`). The object key names the tenant and user;
the finding is recorded once, content-free (identifier types and counts, severity, finding ID), and the
tenant's pipeline is paused until an admin resumes it. Findings never hold the sensitive values
themselves (Macie reports locations only; "reveal samples" is never enabled).
"""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from vanimo.backstops import Backstops
from vanimo.backstops.snapshots import clean_etag
from vanimo.db.session import UserRef
from vanimo.logs import get_logger

log = get_logger("vanimo.backstops")

POLL_EVERY_S = 900
LOOKBACK_DAYS = 3  # findings are recorded once by ID, so overlapping windows are harmless
MAX_PAGES = 20
_KEY = re.compile(r"^l1/([0-9a-f\-]{36})/([0-9a-f\-]{36})\.jsonl$")


@dataclass(frozen=True)
class MacieFinding:
    finding_id: str
    ref: UserRef
    kinds: dict[str, int]
    severity: str | None
    etag: str | None = None  # the scanned object's ETag: which export the line numbers refer to
    records: tuple[int, ...] = ()  # JSON Lines line numbers (Macie reports up to 15 per detection)


def _records(detection: dict[str, Any]) -> list[int]:
    out: list[int] = []
    for r in (detection.get("occurrences") or {}).get("records") or []:
        idx = r.get("recordIndex")
        if isinstance(idx, int) and 0 <= idx < 10_000_000:
            out.append(idx)
    return out


def parse(finding: dict[str, Any], bucket: str) -> MacieFinding | None:
    """A sensitive-data finding on one of our snapshot objects, or None (another bucket, a policy
    finding, a key that isn't a snapshot)."""
    res = finding.get("resourcesAffected") or {}
    if (res.get("s3Bucket") or {}).get("name") != bucket or finding.get("category") != "CLASSIFICATION":
        return None
    m = _KEY.match((res.get("s3Object") or {}).get("key") or "")
    if not m:
        return None
    try:
        ref = UserRef(uuid.UUID(m.group(1)), uuid.UUID(m.group(2)))
    except ValueError:
        return None
    finding_id = re.sub(r"[^A-Za-z0-9_.:/\-]", "", str(finding.get("id") or ""))[:160]
    if not finding_id:
        return None
    result = (finding.get("classificationDetails") or {}).get("result") or {}
    kinds: Counter[str] = Counter()
    records: list[int] = []
    for group in result.get("sensitiveData") or []:
        for d in group.get("detections") or []:
            kinds[_kind(d.get("type"), "UNKNOWN")] += _count(d.get("count"))
            records += _records(d)
    for d in (result.get("customDataIdentifiers") or {}).get("detections") or []:
        kinds[_kind(d.get("name"), "custom")] += _count(d.get("count"))
        records += _records(d)
    severity = str((finding.get("severity") or {}).get("description", "")).lower() or None
    return MacieFinding(
        finding_id,
        ref,
        dict(kinds) or {"unspecified": 1},
        severity if severity in ("low", "medium", "high") else None,
        clean_etag((res.get("s3Object") or {}).get("eTag")) or None,
        tuple(sorted(set(records))[:200]),
    )


def _kind(value: Any, default: str) -> str:
    """An identifier type or custom identifier name, cut to what an event may hold."""
    return re.sub(r"[^A-Za-z0-9_:. \-]", "_", str(value or default))[:60] or default


def _count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


class MacieReader:
    def __init__(self, bucket: str, region: str, *, client: Any = None) -> None:
        if client is None:
            import boto3

            client = boto3.client("macie2", region_name=region)
        self._client = client
        self.bucket = bucket

    def _list(self, since_ms: int) -> list[str]:
        ids: list[str] = []
        token: str | None = None
        for _ in range(MAX_PAGES):
            kw: dict[str, Any] = {
                "findingCriteria": {
                    "criterion": {
                        "resourcesAffected.s3Bucket.name": {"eq": [self.bucket]},
                        "category": {"eq": ["CLASSIFICATION"]},
                        "archived": {"eq": ["false"]},
                        "updatedAt": {"gte": since_ms},
                    }
                },
                "sortCriteria": {"attributeName": "updatedAt", "orderBy": "ASC"},
                "maxResults": 50,
            }
            if token:
                kw["nextToken"] = token
            resp = self._client.list_findings(**kw)
            ids += resp.get("findingIds") or []
            token = resp.get("nextToken")
            if not token:
                break
        return ids

    def _get(self, ids: list[str]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for i in range(0, len(ids), 50):
            out += self._client.get_findings(findingIds=ids[i : i + 50]).get("findings") or []
        return out

    async def findings(self, since_ms: int) -> list[MacieFinding]:
        ids = await asyncio.to_thread(self._list, since_ms)
        raw = await asyncio.to_thread(self._get, ids) if ids else []
        return [f for f in (parse(r, self.bucket) for r in raw) if f is not None]


_last_poll = 0.0


async def poll_round(engine: AsyncEngine, backstops: Backstops, *, force: bool = False) -> int:
    """Records new findings (each pauses its tenant). Returns how many were new."""
    global _last_poll
    if backstops.macie_mode != "aws" or backstops.macie_reader is None:
        return 0
    if not force and time.monotonic() - _last_poll < POLL_EVERY_S:
        return 0
    from vanimo.backstops.snapshots import record_finding

    since_ms = int((time.time() - LOOKBACK_DAYS * 86400) * 1000)
    try:
        found = await backstops.macie_reader.findings(since_ms)
    except Exception as exc:
        log.warning("backstops.macie_poll_failed", error_type=type(exc).__name__)
        return 0
    _last_poll = time.monotonic()
    new = failed = 0
    for f in found:
        # One finding that can't be recorded never stops the others from pausing their tenants.
        try:
            if await record_finding(
                engine, f.ref, f.finding_id, f.kinds, f.severity, etag=f.etag, records=list(f.records)
            ):
                new += 1
        except Exception as exc:
            failed += 1
            log.error("backstops.macie_record_failed", error_type=type(exc).__name__)
    if failed:
        _last_poll = 0.0  # try again next round
    return new
