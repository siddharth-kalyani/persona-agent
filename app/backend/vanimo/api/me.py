"""GET /api/me — the M0 demo: who you are, your manager, your last 5 sent subjects.

Read live from Microsoft Graph as the user and never stored (Mode A, D4). Only header
fields are requested — no message text.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from vanimo.aio import gather_strict
from vanimo.api.deps import CurrentPrincipal, CurrentUser, State, UserGraph
from vanimo.db.session import user_tx
from vanimo.graph import metadata

router = APIRouter(prefix="/api", tags=["me"])


class PersonOut(BaseModel):
    displayName: str | None = None
    jobTitle: str | None = None
    department: str | None = None


class SentHeaderOut(BaseModel):
    subject: str | None
    sentDateTime: datetime | None
    recipientCount: int


class MeOut(BaseModel):
    user: PersonOut
    manager: PersonOut | None
    recentSent: list[SentHeaderOut]
    roles: list[str]
    onboardingState: str


@router.get("/me", response_model=MeOut)
async def get_me(principal: CurrentPrincipal, user: CurrentUser, graph: UserGraph, state: State) -> MeOut:
    me, manager, sent = await gather_strict(
        metadata.me(graph), metadata.manager(graph), metadata.recent_sent_headers(graph, top=5)
    )
    async with user_tx(state.engine, user) as conn:
        onboarding = (await conn.execute(text("select onboarding_state from vanimo.users"))).scalar_one()
    return MeOut(
        user=PersonOut(**{k: me.get(k) for k in ("displayName", "jobTitle", "department")}),
        manager=PersonOut(**{k: manager.get(k) for k in ("displayName", "jobTitle")}) if manager else None,
        recentSent=[
            SentHeaderOut(
                subject=m.get("subject"),
                sentDateTime=m.get("sentDateTime"),
                recipientCount=sum(len(m.get(f) or []) for f in ("toRecipients", "ccRecipients", "bccRecipients")),
            )
            for m in sent
        ],
        roles=sorted(principal.roles),
        onboardingState=onboarding,
    )
