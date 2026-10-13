"""Validate Entra ID v2 access tokens issued for the Vanimo API.

Single-tenant (D8): only tokens from the organisation's tenant are accepted. The app
registration must set `accessTokenAcceptedVersion: 2` (see app/infra/entra/README.md).
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

import httpx
import jwt
from jwt import PyJWK

from vanimo.config import Settings
from vanimo.db.session import UserRef

ROLE_USER = "Vanimo.User"
ROLE_ADMIN = "Vanimo.Admin"
# Platform super-admin (architecture §5.3): tenant lifecycle, flags, model routing — never content.
# No super-admin console exists yet (operator scripts until external tenants); it implies admin.
ROLE_SUPERADMIN = "Vanimo.SuperAdmin"
KNOWN_ROLES = frozenset({ROLE_USER, ROLE_ADMIN, ROLE_SUPERADMIN})


class AuthError(Exception):
    """Token rejected. `code` is safe to log and to return to the client."""

    def __init__(self, code: str, status: int = 401) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


@dataclass(frozen=True)
class Principal:
    entra_tenant_id: str
    entra_oid: str
    roles: frozenset[str]
    scopes: frozenset[str]
    # Kept only in memory for the On-Behalf-Of exchange; never logged or stored.
    access_token: str = field(repr=False)
    # "entra" (Microsoft sign-in) or "password" (local/dev email + password sign-in).
    auth_method: str = "entra"
    # Password sessions already know their user; Entra principals are provisioned on first use.
    local_user: UserRef | None = None
    email: str | None = field(default=None, repr=False)
    must_change_password: bool = False

    @property
    def is_admin(self) -> bool:
        return ROLE_ADMIN in self.roles or ROLE_SUPERADMIN in self.roles

    @property
    def is_superadmin(self) -> bool:
        return ROLE_SUPERADMIN in self.roles


class JwksCache:
    """Caches the tenant's signing keys; refetches on an unknown `kid` at most once a minute.

    If a refresh fails, keys already cached keep working (Entra rotates keys weeks apart), so a
    short Entra outage doesn't block every sign-in."""

    def __init__(self, url: str, http: httpx.AsyncClient, ttl_s: float = 3600, min_refresh_s: float = 60):
        self._url = url
        self._http = http
        self._ttl = ttl_s
        self._min_refresh = min_refresh_s
        self._keys: dict[str, PyJWK] = {}
        self._fetched_at = 0.0
        self._last_attempt = float("-inf")
        self._lock = asyncio.Lock()

    async def _refresh(self) -> None:
        resp = await self._http.get(self._url, timeout=10)
        resp.raise_for_status()
        keys: dict[str, PyJWK] = {}
        for jwk in resp.json().get("keys", []):
            if jwk.get("kty") == "RSA" and jwk.get("kid") and jwk.get("use", "sig") == "sig":
                keys[jwk["kid"]] = PyJWK(jwk, algorithm="RS256")
        self._keys = keys
        self._fetched_at = time.monotonic()

    async def get(self, kid: str) -> PyJWK:
        now = time.monotonic()
        if kid in self._keys and now - self._fetched_at < self._ttl:
            return self._keys[kid]
        async with self._lock:
            now = time.monotonic()
            if kid not in self._keys or now - self._fetched_at >= self._ttl:
                # Rate-limit attempts, failed ones included, so an Entra outage doesn't make every
                # request wait on a fetch.
                if now - self._last_attempt >= self._min_refresh:
                    self._last_attempt = now
                    try:
                        await self._refresh()
                    except (httpx.HTTPError, ValueError) as exc:
                        if kid not in self._keys:
                            raise AuthError("jwks_unavailable", 503) from exc
        if not self._keys:
            raise AuthError("jwks_unavailable", 503)
        if kid not in self._keys:
            raise AuthError("unknown_signing_key")
        return self._keys[kid]


class TokenValidator:
    def __init__(self, settings: Settings, jwks: JwksCache) -> None:
        self._s = settings
        self._jwks = jwks

    async def validate(self, token: str) -> Principal:
        if not (self._s.entra_tenant_id and self._s.entra_client_id):
            raise AuthError("microsoft_signin_not_configured")
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise AuthError("malformed_token") from exc
        if header.get("alg") != "RS256" or not header.get("kid"):
            raise AuthError("unsupported_token_alg")
        key = await self._jwks.get(header["kid"])
        try:
            claims = jwt.decode(
                token,
                key=key.key,
                algorithms=["RS256"],
                audience=self._s.api_audiences,
                issuer=self._s.entra_issuer,
                leeway=60,
                options={"require": ["exp", "iat", "nbf", "aud", "iss", "tid", "oid"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthError("token_expired") from exc
        except jwt.PyJWTError as exc:
            raise AuthError("invalid_token") from exc

        if claims.get("tid") != self._s.entra_tenant_id:
            raise AuthError("wrong_tenant", 403)
        if claims.get("ver") != "2.0":
            raise AuthError("unsupported_token_version")
        # Only Vanimo's own clients (web app, add-in) may call the API. Another app in the tenant that
        # obtained `access_as_user` must not be able to use Vanimo's Graph permissions through OBO.
        if claims.get("azp") != self._s.entra_client_id:
            raise AuthError("unauthorized_client", 403)
        scopes = frozenset(str(claims.get("scp", "")).split())
        if self._s.api_scope_name not in scopes:
            # App-only tokens (no `scp`) are never accepted on user endpoints.
            raise AuthError("missing_scope", 403)
        # Super-admin is a platform (Vanimo staff) role: never taken from a customer's Entra token,
        # where that customer's own admin could assign it. It comes only from server-side accounts.
        roles = frozenset(r for r in claims.get("roles", []) if r in KNOWN_ROLES and r != ROLE_SUPERADMIN)
        if not roles:
            # "Assignment required" in Entra should stop this earlier; enforce it here too.
            raise AuthError("not_assigned", 403)
        return Principal(
            entra_tenant_id=claims["tid"],
            entra_oid=claims["oid"],
            roles=roles,
            scopes=scopes,
            access_token=token,
        )
