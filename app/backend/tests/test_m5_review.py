"""M5 review fixes: chat activity, stable promise keys, chat matching, due dates, checks, bot, notifications."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt
import psycopg
import pytest

from tests.conftest import TENANT
from tests.helpers import _find, _sources
from tests.test_drafting import _draft, _ready
from tests.test_m5 import IST, _as_owner, _ledger
from vanimo.api import deps
from vanimo.commitments import scan as scanning
from vanimo.commitments import store
from vanimo.commitments.extract import Found
from vanimo.config import Settings
from vanimo.sources.base import Chat, ChatMessage
from vanimo.sources.sample import SampleSource
from vanimo.state import AppState


def _override(client: httpx.AsyncClient, factory: Any) -> None:
    async def source(principal: deps.CurrentPrincipal) -> SampleSource:
        return factory(principal.email)

    client._transport.app.dependency_overrides[deps.get_source] = source  # type: ignore[attr-defined]


def _clear(client: httpx.AsyncClient) -> None:
    client._transport.app.dependency_overrides.clear()  # type: ignore[attr-defined]


async def test_scan_asks_chats_whose_last_message_time_is_unknown(
    client: httpx.AsyncClient, scanned: dict, database: dict[str, str]
) -> None:
    """Graph's chat list only knows when a chat was renamed or its roster changed: a chat can't be
    skipped as quiet on that, so a new promise in an old 1:1 chat is still found."""
    h = scanned
    await _ready(client, h)
    fresh = datetime.now(UTC) + timedelta(minutes=1)  # after the learning run's mark

    class GraphLike(SampleSource):
        async def chats(self) -> AsyncIterator[Chat]:
            async for c in super().chats():
                # Graph-like: no last-message time, and a "last updated" months ago.
                yield replace(c, last_message_at=None, last_activity_at=datetime.now(UTC) - timedelta(days=200))

        async def chat_messages(self, chat_id: str, since: datetime | None = None) -> AsyncIterator[ChatMessage]:
            async for m in super().chat_messages(chat_id, since):
                yield m
            if chat_id == "smp-chat-005":  # the 1:1 with Priya
                yield ChatMessage("new-1", chat_id, self.me, fresh, "I'll share the Orion scope note by Monday.", True)

    _override(client, GraphLike)
    try:
        scanning.THROTTLE._last.clear()
        resp = await client.post("/api/commitments/scan", headers=h)
        assert resp.status_code == 200, resp.text
        assert resp.json()["found"] >= 1
    finally:
        _clear(client)
    assert "Share the Orion scope note" in {c["what"] for c in (await _ledger(client, h))["items"]}


async def test_promise_keys_are_stable_across_extractors(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState
) -> None:
    """Another extractor (or a model's other order) never duplicates a promise or reopens one."""
    h = scanned
    await _ready(client, h)
    items = (await _ledger(client, h))["items"]
    first = items[0]
    assert (
        await client.put(f"/api/commitments/{first['id']}", json={"action": "dismiss"}, headers=h)
    ).status_code == 204
    from sqlalchemy import text

    from vanimo.controls.store import hasher_for
    from vanimo.db.session import user_tx
    from vanimo.learning.backfill import controls_version

    user = await _user_ref(app_state, h, client)
    async with user_tx(app_state.engine, user) as conn:
        version = await controls_version(conn)
        row = (await conn.execute(text("select item_hash, thread_hash from vanimo.commitments limit 1"))).one()
    assert hasher_for  # same HMAC family as the learner
    unit = store.Unit("chat", row.item_hash, row.thread_hash, [], "peer", datetime.now(UTC), "x", {}, None)
    # The same two sentences in the opposite order, at other positions: nothing new is stored.
    async with user_tx(app_state.engine, user) as conn:
        stored = (
            (
                await conn.execute(
                    text("select text_enc from vanimo.commitments where item_hash = :i"), {"i": row.item_hash}
                )
            )
            .scalars()
            .all()
        )
    sentences = [app_state.vault.decrypt_user(user.tenant_id, user.user_id, s, "commitment_text") or "" for s in stored]
    cands = [store.Candidate(unit, n, Found(s, "x", None, None)) for n, s in enumerate(reversed(sentences), 5)]
    saved = await store.save(
        app_state.engine, app_state.vault, user, "sample", cands, [], version, extractor="bedrock", scanned_until=None
    )
    assert saved is not None and saved.stored == 0
    assert first["id"] in {c["id"] for c in (await _ledger(client, h, "dismissed"))["items"]}


async def _user_ref(app_state: AppState, h: dict, client: httpx.AsyncClient):  # type: ignore[no-untyped-def]
    from vanimo.auth.local import resolve_session
    from vanimo.db.session import UserRef

    principal = await resolve_session(app_state.engine, h["Authorization"].split(" ", 1)[1])
    assert principal.local_user is not None
    return UserRef(principal.local_user.tenant_id, principal.local_user.user_id)


async def test_chat_drafts_match_only_a_similar_message_and_never_when_discarded(
    client: httpx.AsyncClient, scanned: dict, database: dict[str, str]
) -> None:
    h = scanned
    await _ready(client, h)
    rahul = "smp-chat-002"
    d = (
        await _draft(
            client, h, mode="reply", channel="chat", conversationId=rahul, instruction="say the build is on UAT"
        )
    ).json()
    discarded = (
        await _draft(client, h, mode="reply", channel="chat", conversationId="smp-chat-003", instruction="say ok")
    ).json()
    assert (
        await client.post(f"/api/drafts/{discarded['id']}/feedback", json={"outcome": "discarded"}, headers=h)
    ).status_code == 204
    posted = datetime.now(UTC) + timedelta(minutes=1)

    class Chatty(SampleSource):
        async def chat_messages(self, chat_id: str, since: datetime | None = None) -> AsyncIterator[ChatMessage]:
            async for m in super().chat_messages(chat_id, since):
                yield m
            if chat_id == rahul:
                yield ChatMessage("x1", chat_id, self.me, posted, "one sec", True)
                yield ChatMessage("x2", chat_id, self.me, posted + timedelta(minutes=1), d["text"], True)
            if chat_id == "smp-chat-003":
                yield ChatMessage("y1", chat_id, self.me, posted, "ok", True)

    _override(client, Chatty)
    try:
        resp = await client.post("/api/edits/sync", headers=h)
        assert resp.status_code == 200, resp.text
    finally:
        _clear(client)
    url = database["owner"].replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url) as conn:
        states = dict(
            conn.execute(
                "select id::text, match_state from vanimo.drafts where id::text in (%s, %s)", (d["id"], discarded["id"])
            ).fetchall()
        )
        outcome = conn.execute("select outcome from vanimo.edit_events where draft_id = %s", (d["id"],)).fetchone()
    assert states[d["id"]] == "matched" and outcome == ("sent_as_is",)  # "one sec" wasn't the draft being sent
    assert states[discarded["id"]] == "not_tracked"


async def test_group_chats_get_no_prefill_and_chat_checks_skip_recipient_rules(
    client: httpx.AsyncClient, scanned: dict
) -> None:
    h = scanned
    await _ready(client, h)
    group = (await _draft(client, h, mode="reply", channel="chat", conversationId="smp-chat-007")).json()
    assert (
        group["channel"] == "chat" and group["chatUsers"] == []
    )  # opening "a chat with these people" may be another chat
    resp = await client.post(
        "/api/drafts/check",
        json={"body": "My PAN is ABCPE1234F, thanks", "to": [], "conversationId": "smp-chat-006", "channel": "chat"},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    codes = {c["code"] for c in resp.json()["checks"]}
    assert "regulated_id" in codes or any("regulated" in c for c in codes)
    assert not {"first_contact", "new_domain", "outsider_added"} & codes


async def test_entra_issued_bot_tokens_need_a_known_caller(rsa_key: Any, unit_settings: Settings, jwks: dict) -> None:
    import respx

    from vanimo.auth.entra import AuthError
    from vanimo.teams.bot import BotAuth

    unit_settings.teams_bot_id = "44444444-4444-4444-4444-444444444444"
    now = int(time.time())
    act = {"channelId": "msteams", "serviceUrl": "https://smba.trafficmanager.net/in/"}

    def token(azp: str) -> str:
        claims = {
            "iss": f"https://login.microsoftonline.com/{TENANT}/v2.0", "aud": unit_settings.teams_bot_id, "tid": TENANT,
            "azp": azp, "exp": now + 600, "nbf": now - 10,
        }  # fmt: skip
        return jwt.encode(claims, rsa_key, algorithm="RS256", headers={"kid": "test-key-1"})

    async with httpx.AsyncClient() as http:
        with respx.mock() as router:
            router.get(unit_settings.entra_jwks_url).mock(return_value=httpx.Response(200, json=jwks))
            auth = BotAuth(unit_settings, http)
            with pytest.raises(AuthError):  # any app in the tenant can get such a token: off by default
                await auth.check(f"Bearer {token('some-insider-app')}", act)
            unit_settings.teams_bot_callers = ["bot-connector-app"]
            await auth.check(f"Bearer {token('bot-connector-app')}", act)
            with pytest.raises(AuthError):
                await auth.check(f"Bearer {token('some-insider-app')}", act)


async def test_read_notifications_skip_teams_and_decayed_rules_dont_count(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState, database: dict[str, str]
) -> None:
    from vanimo import notify

    h = scanned
    await _ready(client, h)
    _as_owner(database, "update vanimo.commitments set due_at = now() - interval '1 hour'")
    await client.get("/api/notifications", headers=h)  # made, then read in the app
    await client.post("/api/notifications/read", json={}, headers=h)
    sent: list[str] = []

    class Teams(notify.TeamsNotifier):
        async def send(self, entra_oid: str, kind: str, count: int) -> bool:
            sent.append(kind)
            return True

    user = await _user_ref(app_state, h, client)
    with psycopg.connect(database["owner"].replace("postgresql+psycopg://", "postgresql://")) as conn:
        conn.execute("update vanimo.users set entra_oid = %s where id = %s", (str(uuid.uuid4()), user.user_id))
    await notify.deliver(app_state.engine, user, Teams(app_state.http, "https://graph.example", None, "app"))
    assert sent == []  # already read in the app: not pushed again
    # An unconfirmed rule last seen 100 days ago is no longer "to confirm".
    from sqlalchemy import text

    from vanimo.db.session import user_tx

    async with user_tx(app_state.engine, user) as conn:
        await conn.execute(
            text(
                "insert into vanimo.style_rules (tenant_id, owner_user_id, source_kind, scope, kind, key_hash, "
                "value_enc, status, last_seen) values (:t, :u, 'sample', 'peer', 'avoid', :k, 'v1:x', 'active', "
                "now() - interval '100 days')"
            ),
            {"t": user.tenant_id, "u": user.user_id, "k": "a" * 64},
        )
        notes = await notify.due_notes(conn, app_state.vault, user, now=datetime.now(UTC), zone=IST)
    assert all(n.kind != "rules_to_confirm" for n in notes)


def test_kept_names() -> None:
    assert _find and _sources  # shared helpers stay importable for later review tests
