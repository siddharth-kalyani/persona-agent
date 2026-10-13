"""GET /api/me — who you are, your manager, your last 5 sent subjects.

Read live from the user's workspace source and never stored (Mode A, D4): Microsoft Graph for
Microsoft sign-ins, the sample workspace otherwise. Only header fields — no message text.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from vanimo.aio import gather_strict
from vanimo.api.deps import CurrentPrincipal, CurrentUser, State, UserSource
from vanimo.db.session import user_tx
from vanimo.gates import onboarding_state
from vanimo.sources.base import Profile

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
    signInMethod: str
    email: str | None = None
    # "graph" = your Microsoft 365; "sample" = the synthetic Kestrel Analytics workspace.
    dataSource: str
    microsoft365Connected: bool


def _person(p: Profile | None) -> PersonOut | None:
    return PersonOut(displayName=p.display_name, jobTitle=p.job_title, department=p.department) if p else None


@router.get("/me", response_model=MeOut)
async def get_me(principal: CurrentPrincipal, user: CurrentUser, source: UserSource, state: State) -> MeOut:
    async with user_tx(state.engine, user) as conn:
        onboarding, _ = await onboarding_state(conn, source.kind)
    profile, manager, sent = await gather_strict(source.profile(), source.manager(), source.recent_sent(5))
    return MeOut(
        user=_person(profile) or PersonOut(),
        manager=_person(manager),
        recentSent=[
            SentHeaderOut(subject=m.subject, sentDateTime=m.sent_at, recipientCount=len(m.recipients)) for m in sent
        ],
        roles=sorted(principal.roles),
        onboardingState=onboarding,
        signInMethod=principal.auth_method,
        email=principal.email,
        dataSource=source.kind,
        microsoft365Connected=source.kind == "graph",
    )
