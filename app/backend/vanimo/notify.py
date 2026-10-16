"""The notification channel (M5): in the web app, and in the Teams activity feed when configured.

Notifications are content-free by design: a kind, a count and a period ("2 promises due today",
"3 learned rules to confirm"), never a name, subject or promise. The detail is behind sign-in, in
the app. Three kinds:

  * commitments_due — open promises due within a day or overdue (once a day, the user's day);
  * rules_to_confirm — the weekly digest of learned rules waiting for Keep / Not me (M4);
  * review_reminder — the "Choose what Vanimo learns from" review still pending 24 h and 48 h
    after sign-up (M1).

The sweeper makes them (it knows no user content: `notification_candidates()` returns IDs). Each
is then sent to the Teams activity feed if the organisation allows it and the Teams app is set up;
self-notifications need app-only permission (`TeamsActivity.Send`), which no user request carries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from vanimo.controls.store import load_engine
from vanimo.db.session import UserRef, user_tx
from vanimo.edits.rules import DECAY_DAYS
from vanimo.logs import get_logger
from vanimo.vault import Vault

log = get_logger("vanimo.notify")

GUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
ACTIVITY = {  # notification kind → activity type in the Teams manifest
    "commitments_due": "commitmentsDue",
    "rules_to_confirm": "rulesToConfirm",
    "review_reminder": "reviewReminder",
}


@dataclass(frozen=True)
class Note:
    kind: str
    period: str
    count: int


def preview(kind: str, count: int) -> str:
    """The only text a notification carries."""
    if kind == "commitments_due":
        return f"{count} promise{'s' if count != 1 else ''} due soon or overdue"
    if kind == "rules_to_confirm":
        return f"{count} learned rule{'s' if count != 1 else ''} to confirm"
    return "Choose what Vanimo learns from: your review is waiting"


async def due_notes(conn: AsyncConnection, vault: Vault, ref: UserRef, *, now: datetime, zone: Any) -> list[Note]:
    """What this user should be told now. Promises a rule excludes don't count (lineage re-check)."""
    notes: list[Note] = []
    from vanimo.sources.sample import ORG_DOMAIN

    engine = await load_engine(conn, vault, ref)
    sample_engine = await load_engine(conn, vault, ref, extra_org_domains=frozenset({ORG_DOMAIN}))
    rows = (
        await conn.execute(
            text(
                "select source_kind, channel, thread_hash, meeting_hash, series_hash, people from vanimo.commitments "
                "where status = 'open' and due_at is not null and due_at < :soon "
                "and (snoozed_until is null or snoozed_until < :now)"
            ),
            {"soon": now + timedelta(days=1), "now": now},
        )
    ).all()
    due = 0
    for r in rows:
        e = sample_engine if r.source_kind == "sample" else engine
        excluded = e.lineage(
            [(p["p"], list(p["d"])) for p in r.people],
            thread_hash=r.thread_hash if r.channel == "email" else None,
            chat_hash=r.thread_hash if r.channel == "chat" else None,
            meeting_hash=r.meeting_hash,
            series_hash=r.series_hash,
        ).excluded
        due += 0 if excluded else 1
    if due:
        notes.append(Note("commitments_due", now.astimezone(zone).strftime("%Y-%m-%d"), due))
    # Only rules still in use: an unconfirmed rule stops after 90 days without an observation (M4).
    active = (
        await conn.execute(
            text("select count(*) from vanimo.style_rules where status = 'active' and last_seen > :cutoff"),
            {"cutoff": now - timedelta(days=DECAY_DAYS)},
        )
    ).scalar_one()
    if active:
        year, week, _ = now.astimezone(zone).isocalendar()
        notes.append(Note("rules_to_confirm", f"{year}-W{week:02d}", active))
    user = (await conn.execute(text("select onboarding_state, created_at from vanimo.users"))).one()
    if user.onboarding_state == "review_pending":
        age = now - user.created_at
        if age >= timedelta(hours=48):
            notes.append(Note("review_reminder", "r48", 1))
        elif age >= timedelta(hours=24):
            notes.append(Note("review_reminder", "r24", 1))
    return notes


async def produce(engine: AsyncEngine, vault: Vault, ref: UserRef, *, zone: Any, now: datetime | None = None) -> int:
    """Records this user's new notifications (one per kind and period). Returns how many."""
    now = now or datetime.now(UTC)
    made = 0
    async with user_tx(engine, ref) as conn:
        for n in await due_notes(conn, vault, ref, now=now, zone=zone):
            row = await conn.execute(
                text(
                    "insert into vanimo.notifications (tenant_id, owner_user_id, kind, period, count) "
                    "values (:t, :u, :k, :p, :c) on conflict (owner_user_id, kind, period) do nothing returning id"
                ),
                {"t": ref.tenant_id, "u": ref.user_id, "k": n.kind, "p": n.period, "c": n.count},
            )
            made += 1 if row.first() else 0
    return made


class TeamsNotifier:
    """Sends pending notifications to the Teams activity feed (Graph, app-only)."""

    def __init__(self, http: httpx.AsyncClient, graph_base_url: str, app_token: Any, teams_app_id: str) -> None:
        self._http = http
        self._base = graph_base_url.rstrip("/")
        self._token = app_token  # async () -> str
        self._app_id = teams_app_id

    def deep_link(self) -> str:
        # The Vanimo personal tab in Teams (activity feed links must be Teams deep links).
        return f"https://teams.microsoft.com/l/entity/{quote(self._app_id)}/home"

    async def send(self, entra_oid: str, kind: str, count: int) -> bool:
        if not GUID.match(entra_oid):
            return False
        token = await self._token()
        body = {
            "topic": {"source": "text", "value": "Vanimo", "webUrl": self.deep_link()},
            "activityType": ACTIVITY[kind],
            "previewText": {"content": preview(kind, count)},
            "templateParameters": [{"name": "count", "value": str(count)}],
        }
        resp = await self._http.post(
            f"{self._base}/users/{entra_oid}/teamwork/sendActivityNotification",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )
        return resp.status_code in (200, 202, 204)


MAX_ATTEMPTS = 3


async def deliver(engine: AsyncEngine, ref: UserRef, notifier: TeamsNotifier | None) -> int:
    """Pending notifications (and failed ones, up to 3 tries) go to Teams; 'off' when Teams isn't
    available or the person already read it in the app."""
    sent = 0
    async with user_tx(engine, ref) as conn:
        pending = (
            await conn.execute(
                text(
                    "select id, kind, count, read_at from vanimo.notifications where teams_state = 'pending' "
                    "or (teams_state = 'failed' and teams_attempts < :max) order by created_at"
                ),
                {"max": MAX_ATTEMPTS},
            )
        ).all()
        if not pending:
            return 0
        allowed = (
            await conn.execute(text("select teams_notifications from vanimo.tenant_policies"))
        ).scalar_one_or_none()
        oid = (await conn.execute(text("select entra_oid from vanimo.users"))).scalar_one()
    for n in pending:
        if n.read_at is not None or notifier is None or allowed is False or not GUID.match(oid or ""):
            state = "off"
        else:
            try:
                state = "sent" if await notifier.send(oid, n.kind, n.count) else "failed"
            except Exception as exc:  # the in-app notification still stands
                log.warning("notify.teams_failed", error_type=type(exc).__name__)
                state = "failed"
        sent += state == "sent"
        async with user_tx(engine, ref) as conn:
            await conn.execute(
                text(
                    "update vanimo.notifications set teams_state = :s, "
                    "teams_attempts = teams_attempts + case when :s = 'off' then 0 else 1 end where id = :id"
                ),
                {"s": state, "id": n.id},
            )
    return sent


async def run_once(engine: AsyncEngine, vault: Vault, *, zone: Any, notifier: TeamsNotifier | None) -> int:
    """One sweep: every candidate user's notifications made and delivered. Returns how many made."""
    async with engine.begin() as conn:
        users = (await conn.execute(text("select * from vanimo_private.notification_candidates(500)"))).all()
    made = 0
    for u in users:
        ref = UserRef(u.tenant_id, u.user_id)
        try:
            made += await produce(engine, vault, ref, zone=zone)
            await deliver(engine, ref, notifier)
        except Exception as exc:  # one user's failure never stops the others
            log.warning("notify.failed", error_type=type(exc).__name__)
    if made:
        log.info("notify.done", count=made)
    return made


def notifier_for(state: Any) -> TeamsNotifier | None:
    """Teams delivery needs the Teams app (its ID) and the Entra app's secret (app-only token)."""
    if not state.settings.teams_app_id or state.obo is None:
        return None
    return TeamsNotifier(state.http, state.settings.graph_base_url, state.obo.app_token, state.settings.teams_app_id)


async def notify_round(state: Any) -> int:
    return await run_once(state.engine, state.vault, zone=state.settings.cell_config.zone, notifier=notifier_for(state))
