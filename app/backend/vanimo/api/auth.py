"""/api/auth — sign-in options, and local email + password sign-in (local/dev only)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from vanimo import audit
from vanimo.api.deps import CurrentPrincipal, State
from vanimo.auth import local
from vanimo.auth.entra import KNOWN_ROLES, AuthError
from vanimo.auth.passwords import WeakPassword, check_new_password, hash_password, new_session_token
from vanimo.db.session import UserRef, user_tx
from vanimo.logs import get_logger

log = get_logger("vanimo.auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthConfigOut(BaseModel):
    passwordSignIn: bool
    microsoftSignIn: bool


@router.get("/config", response_model=AuthConfigOut)
async def auth_config(state: State) -> AuthConfigOut:
    s = state.settings
    return AuthConfigOut(
        passwordSignIn=s.enable_password_auth, microsoftSignIn=bool(s.entra_tenant_id and s.entra_client_id)
    )


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class SessionOut(BaseModel):
    token: str
    expiresAt: datetime
    mustChangePassword: bool
    roles: list[str]


def _enabled(request: Request) -> None:
    if not request.app.state.vanimo.settings.enable_password_auth:
        raise HTTPException(404)


async def _audit(state: State, ref: UserRef, action: str, request: Request) -> None:
    async with user_tx(state.engine, ref) as conn:
        await audit.record(conn, ref, action, request_id=request.state.request_id)


def _client_key(request: Request) -> str:
    # request.client is the proxy-resolved address; uvicorn trusts X-Forwarded-For only from
    # FORWARDED_ALLOW_IPS (the VPC range in AWS), so clients can't spoof it.
    return request.client.host if request.client else "unknown"


async def _verify(state: State, request: Request, email: str, password: str) -> local.LoginResult:
    """Check a password with throttling, and audit failures against the account when it exists."""
    state.login_throttle.check("ip:" + _client_key(request))
    state.login_throttle.check("email:" + email.lower())
    try:
        return await local.check_credentials(state.engine, email, password)
    except local.LoginFailed as exc:
        log.info("auth.password_login", outcome="locked" if exc.locked else "failed")
        if exc.user is not None:
            await _audit(
                state, exc.user, "auth.account_locked" if exc.locked else "auth.password_login_failed", request
            )
        raise


@router.post("/login", response_model=SessionOut)
async def login(body: LoginIn, state: State, request: Request) -> SessionOut:
    _enabled(request)
    result = await _verify(state, request, body.email.strip(), body.password)
    roles = sorted(r for r in result.roles if r in KNOWN_ROLES)
    if not roles:
        raise AuthError("not_assigned", 403)
    token = new_session_token()
    expires = await local.create_session(state.engine, result, token, state.settings.session_ttl_s)
    await _audit(state, result.user, "auth.password_login", request)
    log.info("auth.password_login", outcome="ok")
    return SessionOut(token=token, expiresAt=expires, mustChangePassword=result.must_change, roles=roles)


class SessionInfoOut(BaseModel):
    method: str
    email: str | None
    roles: list[str]
    mustChangePassword: bool


@router.get("/session", response_model=SessionInfoOut)
async def session_info(principal: CurrentPrincipal) -> SessionInfoOut:
    return SessionInfoOut(
        method=principal.auth_method,
        email=principal.email,
        roles=sorted(principal.roles),
        mustChangePassword=principal.must_change_password,
    )


class ChangePasswordIn(BaseModel):
    currentPassword: str = Field(min_length=1, max_length=256)
    newPassword: str = Field(min_length=1, max_length=256)


def _bearer(request: Request) -> str:
    return request.headers.get("authorization", "").partition(" ")[2].strip()


@router.post("/change-password", response_model=SessionOut)
async def change_password(
    body: ChangePasswordIn, principal: CurrentPrincipal, state: State, request: Request
) -> SessionOut:
    """Allowed even while a password change is required. Ends every session; returns a new one."""
    _enabled(request)
    if principal.auth_method != "password" or not principal.email or principal.local_user is None:
        raise AuthError("password_signin_only", 400)
    result = await _verify(state, request, principal.email, body.currentPassword)
    try:
        check_new_password(body.newPassword, email=principal.email, current=body.currentPassword)
    except WeakPassword as exc:
        raise HTTPException(422, detail={"error": exc.code}) from exc
    new_hash = await local.run_scrypt(hash_password, body.newPassword)
    await local.change_password(state.engine, _bearer(request), new_hash)
    token = new_session_token()
    expires = await local.create_session(state.engine, result, token, state.settings.session_ttl_s)
    await _audit(state, principal.local_user, "auth.password_changed", request)
    return SessionOut(token=token, expiresAt=expires, mustChangePassword=False, roles=sorted(principal.roles))


@router.post("/logout", status_code=204)
async def logout(principal: CurrentPrincipal, state: State, request: Request) -> None:
    if principal.auth_method == "password":
        await local.revoke_session(state.engine, _bearer(request))
        if principal.local_user:
            await _audit(state, principal.local_user, "auth.logout", request)
