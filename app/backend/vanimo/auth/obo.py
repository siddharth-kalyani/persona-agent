"""On-Behalf-Of exchange: the user's API token -> a delegated Microsoft Graph token.

MSAL is synchronous, so calls run in a worker thread. MSAL's in-memory cache keys OBO
tokens by the incoming assertion, so repeated calls in a session don't hit Entra.
"""

from __future__ import annotations

import anyio
import msal
import requests

from vanimo.auth.entra import AuthError, Principal
from vanimo.config import Settings

GRAPH_DEFAULT_SCOPE = ["https://graph.microsoft.com/.default"]


class ConsentRequired(AuthError):
    def __init__(self) -> None:
        super().__init__("consent_required", 403)


class OboClient:
    def __init__(self, settings: Settings, client_secret: str) -> None:
        self._settings = settings
        self._secret = client_secret
        self._app: msal.ConfidentialClientApplication | None = None

    def _client(self) -> msal.ConfidentialClientApplication:
        # Built on first use, in a worker thread: MSAL's constructor fetches tenant metadata over
        # the network, which must not block startup or the event loop.
        if self._app is None:
            self._app = msal.ConfidentialClientApplication(
                client_id=self._settings.entra_client_id,
                client_credential=self._secret,
                authority=f"{self._settings.entra_authority_host}/{self._settings.entra_tenant_id}",
                # Single-tenant: no instance discovery round-trips for other clouds.
                instance_discovery=False,
            )
        return self._app

    async def graph_token(self, principal: Principal) -> str:
        try:
            result = await anyio.to_thread.run_sync(
                lambda: self._client().acquire_token_on_behalf_of(
                    user_assertion=principal.access_token, scopes=GRAPH_DEFAULT_SCOPE
                )
            )
        except (ValueError, requests.RequestException) as exc:  # tenant discovery / network failure
            raise AuthError("entra_unavailable", 503) from exc
        if "access_token" in result:
            return result["access_token"]
        error = result.get("error", "obo_failed")
        if error in ("invalid_grant", "interaction_required", "consent_required"):
            raise ConsentRequired()
        raise AuthError("obo_failed", 502)
