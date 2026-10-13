"""Keeps background work durable across restarts (in-process tasks die with the process).

Every few minutes: scans still "running" after 30 minutes are marked failed (so the UI offers a
retry instead of spinning), and purge/scrub jobs left pending or running are run again (they are
idempotent). Uses SECURITY DEFINER functions from migration 0005, which return IDs only.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from vanimo.controls.jobs import run_job
from vanimo.db.session import UserRef
from vanimo.logs import get_logger
from vanimo.vault import Vault

log = get_logger("vanimo.sweeper")
STALE_SCAN_MINUTES = 30
STALE_JOB_MINUTES = 2
INTERVAL_S = 300


async def sweep_once(engine: AsyncEngine, vault: Vault) -> tuple[int, int]:
    async with engine.begin() as conn:
        failed = (
            await conn.execute(text("select vanimo_private.fail_stale_scans(:m)"), {"m": STALE_SCAN_MINUTES})
        ).scalar_one()
        jobs = (
            await conn.execute(text("select * from vanimo_private.stale_purge_jobs(:m)"), {"m": STALE_JOB_MINUTES})
        ).all()
    for job in jobs:
        await run_job(engine, vault, UserRef(job.tenant_id, job.user_id), str(job.job_id), job.reason)
    if failed or jobs:
        log.info("sweeper.done", count=len(jobs), outcome=f"scans_failed_{failed}")
    return failed, len(jobs)


async def sweep_forever(engine: AsyncEngine, vault: Vault) -> None:
    while True:
        try:
            await sweep_once(engine, vault)
        except Exception as exc:  # keep sweeping; the next round retries
            log.warning("sweeper.failed", error_type=type(exc).__name__)
        await asyncio.sleep(INTERVAL_S)
