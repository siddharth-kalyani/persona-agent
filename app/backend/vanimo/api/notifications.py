"""In-app notifications (M5): content-free counts, the same ones Teams gets.

* GET  /api/notifications       — recent notifications (made for you first, so the bell is current
                                   without waiting for the sweeper).
* POST /api/notifications/read  — mark all (or one) as read.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import text

from vanimo.api.deps import CurrentUser, State
from vanimo.db.session import user_tx
from vanimo.notify import preview, produce

router = APIRouter(prefix="/api", tags=["notifications"])

Kind = Literal["commitments_due", "rules_to_confirm", "review_reminder"]


class NotificationOut(BaseModel):
    id: str
    kind: Kind
    count: int
    text: str
    createdAt: datetime
    read: bool
    teams: Literal["pending", "sent", "failed", "off"]


class NotificationsOut(BaseModel):
    items: list[NotificationOut]
    unread: int


@router.get("/notifications", response_model=NotificationsOut)
async def list_notifications(user: CurrentUser, state: State) -> NotificationsOut:
    await produce(state.engine, state.vault, user, zone=state.settings.cell_config.zone)
    async with user_tx(state.engine, user) as conn:
        rows = (
            await conn.execute(
                text(
                    "select id, kind, count, created_at, read_at, teams_state from vanimo.notifications "
                    "order by created_at desc limit 20"
                )
            )
        ).all()
        unread = (
            await conn.execute(text("select count(*) from vanimo.notifications where read_at is null"))
        ).scalar_one()
    return NotificationsOut(
        items=[
            NotificationOut(
                id=str(r.id),
                kind=r.kind,
                count=r.count,
                text=preview(r.kind, r.count),
                createdAt=r.created_at,
                read=r.read_at is not None,
                teams=r.teams_state,
            )
            for r in rows
        ],
        unread=unread,
    )


class ReadIn(BaseModel):
    id: uuid.UUID | None = None  # omitted: all


@router.post("/notifications/read", status_code=204)
async def mark_read(body: ReadIn, user: CurrentUser, state: State) -> Response:
    async with user_tx(state.engine, user) as conn:
        await conn.execute(
            text(
                "update vanimo.notifications set read_at = now() where read_at is null "
                "and (cast(:id as uuid) is null or id = cast(:id as uuid))"
            ),
            {"id": str(body.id) if body.id else None},
        )
    return Response(status_code=204)
