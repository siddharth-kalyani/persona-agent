"""Teams endpoints (M5).

* POST /api/teams/messages — the bot endpoint Teams calls for the message actions (Bot Framework
                             authentication; IDs only, see `vanimo/teams/bot.py`).
* POST /api/teams/dialog   — the dialog page, signed in as you, turns its handle into the chat and
                             message to draft for (only for the person the handle was made for).
* GET  /api/teams/config   — what the Teams surfaces may offer: "Open chat with the text" (your
                             organisation's switch, after the prefill spike) or Copy only.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from vanimo.api.deps import CurrentPrincipal, CurrentUser, State
from vanimo.auth.entra import AuthError
from vanimo.db.session import user_tx
from vanimo.teams.bot import BotAuth, fetch_task, open_handle

router = APIRouter(prefix="/api/teams", tags=["teams"])

MAX_ACTIVITY_BYTES = 256 * 1024


def _bot_auth(state: Any) -> BotAuth:
    auth = getattr(state, "_bot_auth", None)
    if auth is None:
        auth = BotAuth(state.settings, state.http)
        state._bot_auth = auth
    return auth


@router.post("/messages", include_in_schema=False)
async def bot_messages(request: Request, state: State) -> Response:
    raw = await request.body()
    if len(raw) > MAX_ACTIVITY_BYTES:
        return Response(status_code=413)
    try:
        activity = json.loads(raw)
    except ValueError:
        return Response(status_code=400)
    if not isinstance(activity, dict):
        return Response(status_code=400)
    await _bot_auth(state).check(request.headers.get("authorization", ""), activity)
    if activity.get("type") != "invoke":
        return Response(status_code=200)  # no chat with the bot in the MVP (the personal agent is v1.5)
    name = activity.get("name")
    if name == "composeExtension/fetchTask":
        return JSONResponse(fetch_task(state.settings, state.vault, activity))
    if name == "composeExtension/submitAction":
        return Response(status_code=200)  # the dialog copies or opens the chat itself: nothing to post
    return Response(status_code=200)


class DialogIn(BaseModel):
    handle: str = Field(min_length=10, max_length=2048)


class DialogOut(BaseModel):
    mode: Literal["reply", "new", "channel"]
    chatId: str | None
    messageId: str | None


@router.post("/dialog", response_model=DialogOut)
async def dialog_target(body: DialogIn, principal: CurrentPrincipal, state: State) -> DialogOut:
    if principal.auth_method != "entra":
        raise AuthError("microsoft_signin_required", 409)
    t = open_handle(state.vault, body.handle, tenant=principal.entra_tenant_id, oid=principal.entra_oid)
    return DialogOut(mode=t.mode, chatId=t.chat_id, messageId=t.message_id)  # type: ignore[arg-type]


class TeamsConfigOut(BaseModel):
    prefill: bool  # "Open chat with this text" (else Copy only)
    appId: str | None


@router.get("/config", response_model=TeamsConfigOut)
async def teams_config(user: CurrentUser, state: State) -> TeamsConfigOut:
    async with user_tx(state.engine, user) as conn:
        prefill = (await conn.execute(text("select teams_prefill from vanimo.tenant_policies"))).scalar_one_or_none()
    return TeamsConfigOut(prefill=bool(prefill), appId=state.settings.teams_app_id or None)
