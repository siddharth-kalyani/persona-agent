"""Admin view of the redaction backstops (F11): which service runs (or its labelled stand-in), whether the
organisation's pipeline is paused by a Macie finding, and what the backstops caught (content-free).

* GET  /api/admin/backstops            — status, pause, recent events
* POST /api/admin/backstops/probe      — live check of each service with synthetic text (never user data)
* POST /api/admin/backstops/snapshots  — export the tenant's L1 snapshots now (offline: scanned at once)
* POST /api/admin/backstops/events/{id}/purge — delete the rows a snapshot finding names (audited; the
                                         admin never sees them)
* POST /api/admin/backstops/resume     — clear the pause after the finding was dealt with (audited)
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text

from vanimo import audit
from vanimo.api.deps import AdminPrincipal, CurrentUser, State
from vanimo.backstops import macie, snapshots
from vanimo.backstops.guardrail import GuardrailBlocked
from vanimo.db.session import user_tx

router = APIRouter(prefix="/api/admin/backstops", tags=["admin"])

# Synthetic, made-up values: a probe never sends user content anywhere.
PROBE_TEXT = (
    "Probe from Vanimo. Contact Rahul Verma at Flat 12, 4 MG Road, Bengaluru 560001, phone +1 415 555 0134, "
    "SSN 123-45-6789."
)
# One made-up Indian identifier per guardrail regex, each checked alone: the built-in PII types would
# block the combined text anyway and hide a regex that doesn't work.
INDIA_PROBES = {
    "aadhaar": "Reference 2341 2341 2346 noted.",
    "pan": "Reference ABCPE1234F noted.",
    "gstin": "Reference 27AAPFU0939F1ZV noted.",
    "ifsc": "Reference HDFC0001234 noted.",
    "upi": "Reference resort.booking@okaxis noted.",
}


class BackstopOut(BaseModel):
    key: Literal["comprehend", "guardrail", "macie"]
    mode: Literal["aws", "offline"]
    label: str


class PauseOut(BaseModel):
    since: datetime
    reason: str
    ref: str | None


class SnapshotOut(BaseModel):
    exportedAt: datetime
    items: int
    stored: bool
    offlineFindings: int | None


class EventOut(BaseModel):
    id: int
    at: datetime
    source: str
    stage: str
    outcome: str
    kinds: dict[str, int]
    severity: str | None
    user: str | None  # the internal user ID (no name or address)
    ref: str
    flaggedItems: int  # rows the finding names (snapshot findings), removable without seeing them
    purgedAt: datetime | None


class StatusOut(BaseModel):
    backstops: list[BackstopOut]
    comprehendScope: str
    snapshotEveryHours: int
    paused: PauseOut | None
    mySnapshot: SnapshotOut | None
    events: list[EventOut]


class ProbeOut(BaseModel):
    key: Literal["comprehend", "guardrail", "guardrail_india", "macie"]
    state: Literal["ok", "warn", "fail"]
    code: str
    ms: float


@router.get("", response_model=StatusOut)
async def status(_: AdminPrincipal, user: CurrentUser, state: State) -> StatusOut:
    b = state.backstops
    async with user_tx(state.engine, user, admin=True) as conn:
        t = (
            await conn.execute(
                text("select pipeline_paused_at, pipeline_pause_reason, pipeline_paused_ref from vanimo.tenants")
            )
        ).one()
        snap = (await conn.execute(text("select * from vanimo.l1_snapshots"))).first()
        rows = (
            await conn.execute(
                text(
                    "select id, occurred_at, source, stage, outcome, kinds, severity, user_id, detail, "
                    "jsonb_array_length(locations) as flagged, purged_at "
                    "from vanimo.backstop_events order by occurred_at desc limit 50"
                )
            )
        ).all()
    return StatusOut(
        backstops=[
            BackstopOut(key="comprehend", mode="aws" if b.pii.name == "comprehend" else "offline", label=b.pii.label),
            BackstopOut(
                key="guardrail", mode="aws" if b.guardrail.name == "bedrock" else "offline", label=b.guardrail.label
            ),
            BackstopOut(key="macie", mode=b.macie_mode, label=b.macie_label),
        ],
        comprehendScope=b.comprehend_scope,
        snapshotEveryHours=b.snapshot_every_hours,
        paused=PauseOut(since=t.pipeline_paused_at, reason=t.pipeline_pause_reason, ref=t.pipeline_paused_ref)
        if t.pipeline_paused_at
        else None,
        mySnapshot=SnapshotOut(
            exportedAt=snap.exported_at, items=snap.items, stored=snap.stored, offlineFindings=snap.offline_findings
        )
        if snap
        else None,
        events=[
            EventOut(
                id=r.id,
                at=r.occurred_at,
                source=r.source,
                stage=r.stage,
                outcome=r.outcome,
                kinds=r.kinds,
                severity=r.severity,
                user=str(r.user_id) if r.user_id else None,
                ref=r.detail,
                flaggedItems=r.flagged,
                purgedAt=r.purged_at,
            )
            for r in rows
        ],
    )


@router.post("/probe", response_model=list[ProbeOut])
async def probe(_: AdminPrincipal, state: State) -> list[ProbeOut]:
    """Each service with made-up PII: Comprehend must find it, the guardrail must block it, and Macie
    findings must be readable. Content-free results only."""
    b = state.backstops
    out: list[ProbeOut] = []

    start = time.perf_counter()
    try:
        found = await b.pii.detect(PROBE_TEXT)
        out.append(_probe("comprehend", "ok" if found else "warn", "found" if found else "nothing_found", start))
    except Exception as exc:
        out.append(_probe("comprehend", "fail", type(exc).__name__, start))

    start = time.perf_counter()
    try:
        await b.guardrail.check("INPUT", [PROBE_TEXT])
        out.append(_probe("guardrail", "warn", "not_blocked", start))
    except GuardrailBlocked:
        out.append(_probe("guardrail", "ok", "blocked", start))
    except Exception as exc:
        out.append(_probe("guardrail", "fail", type(exc).__name__, start))

    start = time.perf_counter()
    missed: list[str] = []
    try:
        for name, sample in INDIA_PROBES.items():
            try:
                await b.guardrail.check("INPUT", [sample])
                missed.append(name)
            except GuardrailBlocked:
                pass
        code = "missed_" + "_".join(missed) if missed else "blocked"
        out.append(_probe("guardrail_india", "warn" if missed else "ok", code, start))
    except Exception as exc:
        out.append(_probe("guardrail_india", "fail", type(exc).__name__, start))

    start = time.perf_counter()
    if b.macie_mode == "aws":
        try:
            await b.macie_reader.findings(int((time.time() - 3600) * 1000))
            out.append(_probe("macie", "ok", "findings_readable", start))
        except Exception as exc:
            out.append(_probe("macie", "fail", type(exc).__name__, start))
    else:
        out.append(_probe("macie", "ok", "offline", start))
    return out


def _probe(key: Any, st: Literal["ok", "warn", "fail"], code: str, start: float) -> ProbeOut:
    return ProbeOut(key=key, state=st, code=code[:60], ms=round((time.perf_counter() - start) * 1000, 1))


@router.post("/snapshots")
async def export_now(_: AdminPrincipal, user: CurrentUser, state: State, request: Request) -> dict[str, Any]:
    counts = await snapshots.export_due(state.engine, state.vault, state.backstops, admin=user)
    new = await macie.poll_round(state.engine, state.backstops, force=True)
    async with user_tx(state.engine, user) as conn:
        await audit.record(conn, user, "backstops.snapshots_exported", request_id=request.state.request_id)
    return {**counts, "newFindings": new}


@router.post("/events/{event_id}/purge")
async def purge_flagged(
    event_id: int, _: AdminPrincipal, user: CurrentUser, state: State, request: Request
) -> dict[str, int]:
    """Deletes the rows a snapshot finding names, in the admin's organisation. The owner's snapshot is
    rewritten by the next sweep (the deletions count as changes), so Macie then sees it without them."""
    async with user_tx(state.engine, user, admin=True) as conn:
        removed = (await conn.execute(text("select vanimo_private.purge_flagged(:e)"), {"e": event_id})).scalar_one()
        if removed < 0:
            raise HTTPException(404, detail={"error": "not_found"})
        await audit.record(
            conn,
            user,
            "backstops.flagged_purged",
            target_kind="backstop_event",
            target_ref=str(event_id),
            request_id=request.state.request_id,
        )
    return {"removed": removed}


@router.post("/resume")
async def resume(_: AdminPrincipal, user: CurrentUser, state: State, request: Request) -> dict[str, bool]:
    async with user_tx(state.engine, user, admin=True) as conn:
        resumed = bool((await conn.execute(text("select vanimo_private.resume_pipeline()"))).scalar_one())
        if resumed:
            await audit.record(conn, user, "backstops.pipeline_resumed", request_id=request.state.request_id)
    return {"resumed": resumed}
