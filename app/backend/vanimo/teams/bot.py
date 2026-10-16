"""The Teams bot endpoint (M5): only what message actions need — no chat with the bot (the personal
agent is v1.5).

Teams sends `composeExtension/fetchTask` when the user picks "Draft reply" on a message (More
actions) or Vanimo under the compose box. We answer within Teams' 5-second limit with a dialog that
loads Vanimo's own page; the drafting happens there, signed in as the user, through the same
drafting service as everywhere else (exclusions on the chat roster first, then the chat's text).

What the invoke carries: the chat ID, the message's ID — and the message's text, which Teams sends
whether we want it or not. Only the IDs are used. The text is never read, logged or stored here: the
dialog's draft reads the chat through Graph, after the exclusion engine allowed the chat.

The IDs go to the dialog in an opaque, encrypted, 10-minute handle bound to the user's Entra
identity, so no chat or message ID ever appears in a URL or a log.

Incoming requests are authenticated as Bot Framework requires: a JWT from the Bot Connector service
(issuer https://api.botframework.com, keys from login.botframework.com with the channel's
endorsement, audience = our bot ID, serviceUrl claim = the activity's), or, as channels move to
Entra-issued tokens, one from our own Entra tenant for the bot ID.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from jwt import PyJWK

from vanimo.auth.entra import AuthError, JwksCache
from vanimo.config import Settings
from vanimo.logs import get_logger
from vanimo.vault import Vault, VaultError

log = get_logger("vanimo.teams")

BOT_FRAMEWORK_KEYS = "https://login.botframework.com/v1/.well-known/keys"
BOT_FRAMEWORK_ISSUER = "https://api.botframework.com"
HANDLE_TTL_S = 600
HANDLE_PURPOSE = "teams_dialog"


class EndorsedJwks(JwksCache):
    """Bot Framework keys, with each key's endorsements (the channels it may sign for)."""

    def __init__(self, url: str, http: httpx.AsyncClient) -> None:
        super().__init__(url, http)
        self.endorsements: dict[str, list[str]] = {}

    async def _refresh(self) -> None:
        resp = await self._http.get(self._url, timeout=10)
        resp.raise_for_status()
        keys: dict[str, PyJWK] = {}
        endorsements: dict[str, list[str]] = {}
        for k in resp.json().get("keys", []):
            if k.get("kty") == "RSA" and k.get("kid"):
                keys[k["kid"]] = PyJWK({x: v for x, v in k.items() if x != "endorsements"}, algorithm="RS256")
                endorsements[k["kid"]] = list(k.get("endorsements") or [])
        self._keys, self.endorsements = keys, endorsements
        self._fetched_at = time.monotonic()


class BotAuth:
    def __init__(self, settings: Settings, http: httpx.AsyncClient) -> None:
        self._s = settings
        self._bf = EndorsedJwks(BOT_FRAMEWORK_KEYS, http)
        self._entra = JwksCache(settings.entra_jwks_url, http)

    async def check(self, authorization: str, activity: dict[str, Any]) -> None:
        bot_id = self._s.teams_bot_id
        if not bot_id:
            raise AuthError("teams_not_configured", 503)
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise AuthError("missing_token")
        try:
            header = jwt.get_unverified_header(token)
            issuer = jwt.decode(token, options={"verify_signature": False}).get("iss")
        except jwt.PyJWTError as exc:
            raise AuthError("malformed_token") from exc
        if header.get("alg") != "RS256" or not header.get("kid"):
            raise AuthError("unsupported_token_alg")
        tenant = self._s.entra_tenant_id
        entra_issuers = [f"https://login.microsoftonline.com/{tenant}/v2.0", f"https://sts.windows.net/{tenant}/"]
        if issuer == BOT_FRAMEWORK_ISSUER:
            key = await self._bf.get(header["kid"])
            channel = str(activity.get("channelId") or "")
            if channel not in self._bf.endorsements.get(header["kid"], []):
                raise AuthError("key_not_endorsed", 403)
            claims = self._decode(token, key, bot_id, BOT_FRAMEWORK_ISSUER)
            if claims.get("serviceUrl") != activity.get("serviceUrl"):
                raise AuthError("service_url_mismatch", 403)
        elif tenant and issuer in entra_issuers:
            claims = self._decode(token, await self._entra.get(header["kid"]), bot_id, issuer)
            if claims.get("tid") not in (None, tenant):
                raise AuthError("wrong_tenant", 403)
        else:
            raise AuthError("invalid_issuer")

    @staticmethod
    def _decode(token: str, key: PyJWK, audience: str, issuer: str) -> dict[str, Any]:
        try:
            return jwt.decode(
                token,
                key=key.key,
                algorithms=["RS256"],
                audience=audience,
                issuer=issuer,
                leeway=300,  # Bot Framework allows 5 minutes of clock skew
                options={"require": ["exp", "aud", "iss"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthError("token_expired") from exc
        except jwt.PyJWTError as exc:
            raise AuthError("invalid_token") from exc


# --- the dialog handle -----------------------------------------------------------------------------
@dataclass(frozen=True)
class DialogTarget:
    mode: str  # reply | new | channel (not supported: chats only)
    chat_id: str | None
    message_id: str | None


def make_handle(vault: Vault, *, tenant: str, oid: str, target: DialogTarget, now: float | None = None) -> str:
    payload = {
        "tid": tenant,
        "oid": oid,
        "mode": target.mode,
        "chat": target.chat_id,
        "msg": target.message_id,
        "exp": int((now or time.time()) + HANDLE_TTL_S),
    }
    return vault.encrypt_app(json.dumps(payload, separators=(",", ":")), HANDLE_PURPOSE)


def open_handle(vault: Vault, handle: str, *, tenant: str, oid: str, now: float | None = None) -> DialogTarget:
    """The dialog's target, only for the user it was made for and only for 10 minutes."""
    try:
        data = json.loads(vault.decrypt_app(handle, HANDLE_PURPOSE))
    except (VaultError, ValueError) as exc:
        raise AuthError("invalid_handle", 403) from exc
    if data.get("exp", 0) < (now or time.time()):
        raise AuthError("handle_expired", 403)
    if data.get("tid") != tenant or data.get("oid") != oid:
        raise AuthError("handle_not_yours", 403)
    return DialogTarget(data["mode"], data.get("chat"), data.get("msg"))


# --- invokes ---------------------------------------------------------------------------------------
def target_of(activity: dict[str, Any]) -> DialogTarget:
    """IDs only: never the message text Teams put in the invoke."""
    value = activity.get("value") or {}
    conversation = activity.get("conversation") or {}
    command = value.get("commandId")
    if conversation.get("conversationType") == "channel" or ";messageid=" in str(conversation.get("id", "")):
        return DialogTarget("channel", None, None)
    chat_id = str(conversation.get("id") or "") or None
    if command == "draftReply":
        message_id = str((value.get("messagePayload") or {}).get("id") or "") or None
        return DialogTarget("reply", chat_id, message_id)
    return DialogTarget("new", chat_id, None)


def fetch_task(settings: Settings, vault: Vault, activity: dict[str, Any]) -> dict[str, Any]:
    tenant = str(((activity.get("channelData") or {}).get("tenant") or {}).get("id") or "")
    oid = str((activity.get("from") or {}).get("aadObjectId") or "")
    if not tenant or tenant != settings.entra_tenant_id or not oid:
        raise AuthError("wrong_tenant", 403)
    target = target_of(activity)
    handle = make_handle(vault, tenant=tenant, oid=oid, target=target)
    url = f"{settings.web_url.rstrip('/')}/teams.html?h={handle}"
    title = "Vanimo: draft a reply" if target.mode == "reply" else "Vanimo: draft a message"
    log.info("teams.fetch_task", outcome=target.mode)
    return {
        "task": {
            "type": "continue",
            "value": {"title": title, "height": "large", "width": "large", "url": url, "fallbackUrl": url},
        }
    }
