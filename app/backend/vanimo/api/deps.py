"""Request dependencies: who is calling, their RLS identity, and a Graph client as them."""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import Depends, Request

from vanimo.auth.entra import AuthError, Principal
from vanimo.db.session import UserRef, provision_user
from vanimo.graph.client import GraphClient
from vanimo.state import AppState


def get_state(request: Request) -> AppState:
    return request.app.state.vanimo


State = Annotated[AppState, Depends(get_state)]


async def get_principal(request: Request, state: State) -> Principal:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthError("missing_token")
    return await state.validator.validate(token.strip())


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


async def get_user(principal: CurrentPrincipal, state: State) -> UserRef:
    """Find or create the caller's tenant + user rows (self-onboarding, D3)."""
    ref = await provision_user(
        state.engine,
        entra_tenant_id=principal.entra_tenant_id,
        entra_oid=principal.entra_oid,
        cell=state.settings.cell,
        data_region=state.settings.cell_config.data_region,
    )
    # Internal UUIDs only — never the Entra object ID, name or e-mail address.
    structlog.contextvars.bind_contextvars(tenant_ref=str(ref.tenant_id), user_ref=str(ref.user_id))
    return ref


CurrentUser = Annotated[UserRef, Depends(get_user)]


async def require_admin(principal: CurrentPrincipal) -> Principal:
    if not principal.is_admin:
        raise AuthError("admin_role_required", 403)
    return principal


AdminPrincipal = Annotated[Principal, Depends(require_admin)]


async def get_graph(principal: CurrentPrincipal, state: State) -> GraphClient:
    if state.obo is None:
        raise AuthError("graph_not_configured", 503)
    token = await state.obo.graph_token(principal)
    # Interactive requests: short backoff so a throttled call fails inside the 60 s edge timeout.
    # At most 3 concurrent calls per request (Exchange allows 4 per app per mailbox).
    return GraphClient(
        token, state.http, state.settings.graph_base_url, max_attempts=3, max_backoff_s=5, max_concurrency=3
    )


UserGraph = Annotated[GraphClient, Depends(get_graph)]
