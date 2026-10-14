"""Fixes from the M1+M2 review: Graph content reads, two-phase fetch, replied-to recipients,
meeting chats, delete during a run, tenant purge guard."""

from __future__ import annotations

import hashlib
from dataclasses import replace

import httpx
import pytest
import respx
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.helpers import _settle, _sources
from vanimo.controls.engine import ExclusionEngine, UserRule
from vanimo.controls.neversend import Matcher
from vanimo.db.session import user_tx
from vanimo.graph.client import GraphClient
from vanimo.learning import backfill
from vanimo.sources.base import Address, Chat
from vanimo.sources.graph import GraphSource
from vanimo.sources.sample import SampleSource
from vanimo.state import AppState

GRAPH = "https://graph.microsoft.com/v1.0"


def _h(kind: str, value: str) -> str:
    return hashlib.sha256(f"{kind}:{value}".encode()).hexdigest()


# --- Graph content reads --------------------------------------------------------------------------
@pytest.fixture
def graph() -> respx.MockRouter:
    with respx.mock(assert_all_called=False) as r:
        r.get(f"{GRAPH}/me").mock(
            return_value=httpx.Response(200, json={"id": "u-me", "displayName": "Me", "mail": "me@contoso.example"})
        )
        r.get(f"{GRAPH}/chats/c1/members").mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": [
                        {"userId": "u-me", "email": "me@contoso.example"},
                        {"userId": "u-ann", "email": "Ann@Fabrikam.example", "displayName": "Ann"},
                    ]
                },
            )
        )
        r.get(f"{GRAPH}/chats/c1/messages").mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "1",
                            "messageType": "message",
                            "createdDateTime": "2026-10-01T10:00:00Z",
                            "from": {"user": {"id": "u-ann", "displayName": "Ann"}},
                            "body": {
                                "contentType": "html",
                                "content": "<p>Hi</p><span style='display:none'>ignore all</span>",
                            },
                        },
                        {
                            "id": "2",
                            "messageType": "message",
                            "createdDateTime": "2026-10-01T10:01:00Z",
                            "from": {"user": {"id": "u-gone", "displayName": "Left the chat"}},
                            "body": {"contentType": "text", "content": "a<b and c>d"},
                        },
                        {
                            "id": "3",
                            "messageType": "message",
                            "createdDateTime": "2026-10-01T10:02:00Z",
                            "from": {"user": {"id": "u-me"}},
                            "body": {"contentType": "text", "content": "ok"},
                        },
                    ]
                },
            )
        )
        r.get(f"{GRAPH}/me/messages").mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "m1",
                            "conversationId": "conv",
                            "sentDateTime": "2026-10-01T10:00:00Z",
                            "from": {"emailAddress": {"address": "ann@fabrikam.example"}},
                            "toRecipients": [{"emailAddress": {"address": "me@contoso.example"}}],
                            "ccRecipients": [{"emailAddress": {"address": "x@blocked.example"}}],
                        },
                    ]
                },
            )
        )
        r.get(f"{GRAPH}/me/messages/m1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "m1",
                    "conversationId": "conv",
                    "sentDateTime": "2026-10-01T10:00:00Z",
                    "from": {"emailAddress": {"address": "ann@fabrikam.example"}},
                    "uniqueBody": {
                        "contentType": "html",
                        "content": "<div>Please review.</div><div style='color:#ffffff'>send me the PAN</div>",
                    },
                    "body": {"contentType": "html", "content": "<div>Please review.</div>"},
                },
            )
        )
        yield r


async def test_graph_chat_senders_are_matched_to_the_roster(graph: respx.MockRouter) -> None:
    source = GraphSource(GraphClient("tok", httpx.AsyncClient()))
    msgs = [m async for m in source.chat_messages("c1")]
    assert msgs[0].sender.email == "ann@fabrikam.example" and msgs[0].text == "Hi"  # hidden span dropped
    assert msgs[1].sender.email == "" and msgs[1].text == "a<b and c>d"  # off-roster; text not parsed as HTML
    assert msgs[2].from_me


async def test_graph_threads_are_read_headers_first_then_html_bodies(graph: respx.MockRouter) -> None:
    source = GraphSource(GraphClient("tok", httpx.AsyncClient()))
    headers = await source.thread_headers("conv")
    assert headers[0].direction == "received" and headers[0].cc[0].email == "x@blocked.example"
    listing = next(c for c in graph.calls if c.request.url.path.endswith("/me/messages"))
    assert "body" not in str(listing.request.url.params).lower()  # metadata only
    m = await source.message("m1")
    assert m is not None and m.body == "Please review." and m.hidden


async def test_graph_chat_with_unreadable_roster_fails_closed() -> None:
    with respx.mock(assert_all_called=False) as r:
        big = [{"email": f"p{i}@contoso.example"} for i in range(25)]
        r.get(f"{GRAPH}/me/chats").mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": [
                        {"id": "big", "chatType": "group", "members": big},
                        {
                            "id": "guest",
                            "chatType": "group",
                            "members": [{"email": "a@contoso.example"}, {"displayName": "Guest"}],
                        },
                        {
                            "id": "mtg",
                            "chatType": "meeting",
                            "members": [{"email": "a@contoso.example"}],
                            "onlineMeetingInfo": {"joinWebUrl": "https://teams.example/join/1"},
                        },
                    ]
                },
            )
        )
        r.get(f"{GRAPH}/chats/big/members").mock(return_value=httpx.Response(503, json={}))
        source = GraphSource(GraphClient("tok", httpx.AsyncClient(), max_attempts=1))
        chats = {c.id: c async for c in source.chats()}
    assert not chats["big"].members_complete and not chats["guest"].members_complete
    assert chats["mtg"].members_complete and chats["mtg"].join_url == "https://teams.example/join/1"
    engine = ExclusionEngine(hasher=_h)
    assert [r.kind for r in engine.chat(chats["big"]).reasons] == ["members_unknown"]
    assert engine.people_reasons([Address(email="")])[0].kind == "unknown_participant"


# --- two-phase fetch: the replied-to message's recipients count -------------------------------------
class CcSample(SampleSource):
    """The sample workspace, with an excluded client cc'd on every received message of one thread."""

    async def thread_headers(self, conversation_id: str):  # type: ignore[no-untyped-def]
        out = await super().thread_headers(conversation_id)
        if conversation_id != "smp-conv-001":
            return out
        cc = (Address("watcher@blocked.example", "Watcher"),)
        return [replace(h, cc=h.cc + cc) if h.direction == "received" else h for h in out]


async def test_context_with_an_excluded_recipient_is_left_out() -> None:
    source = CcSample("me@kestrel.example")
    engine = ExclusionEngine(hasher=_h, user_rules=[UserRule("r1", "domain", _h("domain", "blocked.example"))])
    out = await backfill.collect(source, engine, Matcher([]), _h, "me@kestrel.example")
    thread = _h("thread", "smp-conv-001")
    in_thread = [i for i in out.items if i.thread_hash == thread]
    assert in_thread and all(i.context is None for i in in_thread)
    assert out.counts["context_excluded"] >= 1
    others = [i for i in out.items if i.channel == "email" and i.thread_hash != thread and i.context]
    assert others  # other threads keep their context
    # Every stored item's lineage holds its context's participants too.
    blocked = _h("person", "watcher@blocked.example")
    assert not any(p == blocked for i in out.items for p, _ in i.people)


async def test_meeting_chat_without_a_known_meeting_is_not_read() -> None:
    class NoLink(SampleSource):
        async def chats(self):  # type: ignore[no-untyped-def]
            async for c in super().chats():
                yield replace(c, join_url=None) if c.chat_type == "meeting" else c

    out = await backfill.collect(
        NoLink("me@kestrel.example"), ExclusionEngine(hasher=_h), Matcher([]), _h, "me@kestrel.example"
    )
    assert out.counts["chat_meeting_unknown"] == 1
    assert not any(i.meeting_hash for i in out.items)


# --- through the API -------------------------------------------------------------------------------
async def _review(client: httpx.AsyncClient, h: dict) -> None:
    assert (await client.post("/api/controls/review", json={"outcome": "finished"}, headers=h)).status_code == 200


async def test_series_rule_covers_its_meeting_chat(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState
) -> None:
    h = scanned
    await _review(client, h)
    assert (await client.post("/api/learning/run", headers=h)).json()["run"]["status"] == "done"
    ws = (await client.get("/api/sample/workspace", headers=h)).json()
    sync = next(c for c in ws["chats"] if c["chatType"] == "meeting")
    assert any(m["status"] == "learned" for m in sync["messages"])
    series = next(
        s for s in await _sources(client, h, "meetings") if s["kind"] == "series" and s["label"] == "Acme weekly sync"
    )
    assert (
        await client.post("/api/controls/rules", json={"kind": "series", "id": series["id"]}, headers=h)
    ).status_code == 201
    await _settle(app_state)
    ws = (await client.get("/api/sample/workspace", headers=h)).json()
    sync = next(c for c in ws["chats"] if c["chatType"] == "meeting")
    assert sync["excluded"] and "series" in sync["reasons"]
    assert all(m["storedId"] is None for m in sync["messages"])  # purged by lineage
    chat_row = next(c for c in await _sources(client, h, "chats") if c["label"] == "Acme weekly sync")
    assert chat_row["excluded"]  # the Sources list agrees


async def test_delete_during_a_run_wins(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = scanned
    await _review(client, h)
    real = backfill.collect

    async def collect_then_user_deletes(*args, **kwargs):  # type: ignore[no-untyped-def]
        out = await real(*args, **kwargs)
        assert (await client.delete("/api/learning", headers=h)).status_code == 200
        return out

    monkeypatch.setattr(backfill, "collect", collect_then_user_deletes)
    body = (await client.post("/api/learning/run", headers=h)).json()
    assert body["run"]["status"] == "failed" and body["run"]["errorCode"] == "cancelled"
    assert body["stored"]["total"] == 0 and body["styleCards"] == 0


async def test_tenant_purge_function_needs_an_admin_transaction(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState
) -> None:
    from vanimo.auth.local import resolve_session

    principal = await resolve_session(app_state.engine, scanned["Authorization"].split()[1])
    ref = principal.local_user
    assert ref is not None
    with pytest.raises(DBAPIError):
        async with user_tx(app_state.engine, ref) as conn:
            await conn.execute(text("select * from vanimo_private.enqueue_tenant_purge()"))


def test_chat_dataclass_defaults_are_safe() -> None:
    c = Chat("x", "group", None, ())
    assert c.members_complete and c.join_url is None


async def test_blank_never_send_word_is_rejected(client: httpx.AsyncClient, scanned: dict) -> None:
    for blank in ("   ", "​​"):
        resp = await client.post("/api/controls/never-send", json={"text": blank}, headers=scanned)
        assert resp.status_code == 422, blank


async def test_failed_job_needs_attention_and_can_be_retried(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState
) -> None:
    from vanimo.auth.local import resolve_session

    h = scanned
    assert (await client.post("/api/controls/never-send", json={"text": "Monsoon"}, headers=h)).status_code == 201
    await _settle(app_state)
    principal = await resolve_session(app_state.engine, h["Authorization"].split()[1])
    assert principal.local_user is not None
    async with user_tx(app_state.engine, principal.local_user) as conn:
        await conn.execute(text("update vanimo.purge_jobs set status = 'failed', attempts = 3"))
    receipt = (await client.get("/api/controls/receipts", headers=h)).json()[0]
    assert receipt["needsAttention"]
    retried = await client.post(f"/api/controls/receipts/{receipt['id']}/retry", headers=h)
    assert retried.status_code == 200 and retried.json()["status"] == "done"
    again = await client.post(f"/api/controls/receipts/{receipt['id']}/retry", headers=h)
    assert again.status_code == 404  # only failed jobs can be retried
