"""Request dependencies: who is calling, their RLS identity, and a Graph client as them."""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import Depends, Request

from vanimo.auth.entra import AuthError, Principal
from vanimo.auth.local import resolve_session
from vanimo.auth.passwords import SESSION_PREFIX
from vanimo.backstops.events import ACTING_USER
from vanimo.db.session import UserRef, provision_user
from vanimo.graph.client import GraphClient
from vanimo.sources.base import WorkspaceSource
from vanimo.sources.graph import GraphSource
from vanimo.sources.sample import SampleSource
from vanimo.state import AppState


def get_state(request: Request) -> AppState:
    return request.app.state.vanimo


State = Annotated[AppState, Depends(get_state)]


# Endpoints a password user may call before replacing their one-time password.
PASSWORD_CHANGE_ALLOWED = frozenset({"/api/auth/change-password", "/api/auth/session", "/api/auth/logout"})


async def get_principal(request: Request, state: State) -> Principal:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        raise AuthError("missing_token")
    if token.startswith(SESSION_PREFIX):
        if not state.settings.enable_password_auth:
            raise AuthError("password_signin_disabled")
        principal = await resolve_session(state.engine, token)
        if principal.must_change_password and request.url.path not in PASSWORD_CHANGE_ALLOWED:
            raise AuthError("password_change_required", 403)
        return principal
    return await state.validator.validate(token)


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


async def get_user(principal: CurrentPrincipal, state: State) -> UserRef:
    """Find or create the caller's tenant + user rows (self-onboarding, D3)."""
    if principal.local_user is not None:  # password sessions are already bound to a user
        ref = principal.local_user
        structlog.contextvars.bind_contextvars(tenant_ref=str(ref.tenant_id), user_ref=str(ref.user_id))
        ACTING_USER.set(ref)  # whom a blocked model call is recorded for (vanimo.backstops.events)
        return ref
    ref = await provision_user(
        state.engine,
        entra_tenant_id=principal.entra_tenant_id,
        entra_oid=principal.entra_oid,
        cell=state.settings.cell,
        data_region=state.settings.cell_config.data_region,
    )
    # Internal UUIDs only — never the Entra object ID, name or e-mail address.
    structlog.contextvars.bind_contextvars(tenant_ref=str(ref.tenant_id), user_ref=str(ref.user_id))
    ACTING_USER.set(ref)
    return ref


CurrentUser = Annotated[UserRef, Depends(get_user)]


async def require_admin(principal: CurrentPrincipal) -> Principal:
    if not principal.is_admin:
        raise AuthError("admin_role_required", 403)
    return principal


AdminPrincipal = Annotated[Principal, Depends(require_admin)]


async def get_graph(principal: CurrentPrincipal, state: State) -> GraphClient:
    if principal.auth_method != "entra":
        # Reading Microsoft 365 as the user needs their Microsoft sign-in (On-Behalf-Of).
        raise AuthError("microsoft_signin_required", 409)
    if state.obo is None:
        raise AuthError("graph_not_configured", 503)
    token = await state.obo.graph_token(principal)
    # Interactive requests: short backoff so a throttled call fails inside the 60 s edge timeout.
    # At most 3 concurrent calls per request (Exchange allows 4 per app per mailbox).
    return GraphClient(
        token, state.http, state.settings.graph_base_url, max_attempts=3, max_backoff_s=5, max_concurrency=3
    )


UserGraph = Annotated[GraphClient, Depends(get_graph)]


async def get_source(principal: CurrentPrincipal, state: State) -> WorkspaceSource:
    """The user's workspace metadata: Microsoft Graph, or the sample workspace when Entra/Graph
    isn't available (password sign-in) or sample data is forced (founder decision, 2026-10-13)."""
    if state.settings.sample_data == "always" or principal.auth_method != "entra":
        return SampleSource(principal.email)
    return GraphSource(await get_graph(principal, state))


UserSource = Annotated[WorkspaceSource, Depends(get_source)]
