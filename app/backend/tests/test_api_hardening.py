"""Tests for the M0 review fixes: diagnostics coverage, error handling, timeouts."""

from __future__ import annotations

import httpx
import pytest
import respx
from pydantic import SecretStr

from tests.conftest import FakeObo, TokenFactory
from tests.test_api import CANARY_SUBJECT, GRAPH, _mock_profile
from vanimo.auth.entra import JwksCache, TokenValidator
from vanimo.config import Settings
from vanimo.db.session import make_engine
from vanimo.llm.router import ModelRouter, StreamTiming
from vanimo.state import AppState

pytestmark = pytest.mark.db
ADMIN = {"roles": ("Vanimo.Admin",)}


def _auth(make_token: TokenFactory, **kw: object) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(**kw)}"}


async def test_draft_probe_rejects_ids_that_could_inject_paths(
    client: httpx.AsyncClient, make_token: TokenFactory
) -> None:
    resp = await client.delete("/api/admin/diagnostics/draft-probe/AAMk.bad;id", headers=_auth(make_token, **ADMIN))
    assert resp.status_code == 422 and resp.json() == {"error": "invalid_id"}


async def test_transcript_lookup_escapes_odata_quotes(
    client: httpx.AsyncClient, make_token: TokenFactory, graph_mock: respx.MockRouter
) -> None:
    _mock_profile(graph_mock)
    graph_mock.get(f"{GRAPH}/me/mailFolders/sentitems/messages/delta").mock(
        return_value=httpx.Response(200, json={"value": [], "@odata.deltaLink": "x"})
    )
    graph_mock.get(f"{GRAPH}/me/chats").mock(return_value=httpx.Response(200, json={"value": []}))
    join_url = "https://teams.microsoft.com/l/meetup-join/a'b"
    graph_mock.get(f"{GRAPH}/me/calendarView").mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {"id": "e1", "isOnlineMeeting": True, "isOrganizer": True, "onlineMeeting": {"joinUrl": join_url}}
                ]
            },
        )
    )
    lookup = graph_mock.get(f"{GRAPH}/me/onlineMeetings").mock(
        return_value=httpx.Response(200, json={"value": [{"id": "om1"}]})
    )
    graph_mock.get(f"{GRAPH}/me/onlineMeetings/om1/transcripts").mock(
        return_value=httpx.Response(200, json={"value": [{"id": "t1"}, {"id": "t2"}]})
    )
    resp = await client.post("/api/admin/diagnostics/run", headers=_auth(make_token, **ADMIN))
    results = {r["check"]: r for r in resp.json()["results"]}
    assert results["meeting_transcripts"]["outcome"] == "ok"
    assert results["meeting_transcripts"]["details"]["organizer_transcripts_found"] == 2
    assert lookup.calls.last.request.url.params["$filter"].endswith("a''b'")


async def test_sent_headers_counts_labels_and_forwards(
    client: httpx.AsyncClient, make_token: TokenFactory, graph_mock: respx.MockRouter
) -> None:
    # Registered before the generic profile mocks: respx matches routes in order.
    graph_mock.get(f"{GRAPH}/me/mailFolders/sentitems/messages", params={"$top": "50"}).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "1",
                        "subject": "FW: budget",
                        "conversationId": "c1",
                        "internetMessageHeaders": [{"name": "msip_labels", "value": "x"}],
                    },
                    {"id": "2", "subject": "Re: plan", "internetMessageHeaders": [{"name": "X-Other", "value": "y"}]},
                    {"id": "3", "subject": "Fwd: notes"},
                ]
            },
        )
    )
    _mock_profile(graph_mock)
    for path in ("me/mailFolders/sentitems/messages/delta", "me/chats", "me/calendarView"):
        graph_mock.get(f"{GRAPH}/{path}").mock(return_value=httpx.Response(200, json={"value": []}))
    resp = await client.post("/api/admin/diagnostics/run", headers=_auth(make_token, **ADMIN))
    details = {r["check"]: r for r in resp.json()["results"]}["sent_headers"]["details"]
    assert details == {
        "items": 3,
        "with_internet_headers": 2,
        "with_msip_labels": 1,
        "forwards": 2,
        "forwards_with_conversation_id": 1,
    }
    assert "budget" not in resp.text


async def test_header_pass_timing_counts_only(
    client: httpx.AsyncClient, make_token: TokenFactory, graph_mock: respx.MockRouter
) -> None:
    delta = f"{GRAPH}/me/mailFolders/sentitems/messages/delta"
    graph_mock.get(delta, params={"skip": "1"}).mock(
        return_value=httpx.Response(200, json={"value": [{"subject": CANARY_SUBJECT}] * 2, "@odata.deltaLink": "d"})
    )
    graph_mock.get(delta).mock(
        return_value=httpx.Response(
            200, json={"value": [{"subject": CANARY_SUBJECT}] * 3, "@odata.nextLink": f"{delta}?skip=1"}
        )
    )
    graph_mock.get(f"{GRAPH}/me/chats").mock(return_value=httpx.Response(200, json={"value": [{}, {}]}))
    resp = await client.post("/api/admin/diagnostics/header-pass", headers=_auth(make_token, **ADMIN))
    body = resp.json()
    assert (body["sentItems"], body["sentPages"], body["sentFinished"]) == (5, 2, True)
    assert (body["chats"], body["chatsFinished"]) == (2, True)
    assert CANARY_SUBJECT not in resp.text


async def test_bedrock_latency_reports_min_median_max(
    client: httpx.AsyncClient, make_token: TokenFactory, app_state: AppState
) -> None:
    class FakeLlm:
        def __init__(self) -> None:
            self.n = 0

        async def timed_probe(self, model: str, prompt: str) -> StreamTiming:
            self.n += 1
            if model.endswith("sonnet-5-5") and self.n % 2:
                raise TimeoutError
            return StreamTiming(model_id=model, ttft_ms=100.0 * self.n, total_ms=500.0, output_chars=5)

    app_state._llm = FakeLlm()  # type: ignore[assignment]
    headers = _auth(make_token, **ADMIN)
    resp = await client.post("/api/admin/diagnostics/bedrock-latency", json={"runs": 3}, headers=headers)
    assert resp.status_code == 200, resp.text
    by_model = {r["modelId"]: r for r in resp.json()}
    assert set(by_model) == {"anthropic.claude-haiku-4-5", "anthropic.claude-sonnet-5-5"}
    for r in by_model.values():
        if r["ttftMinMs"] is not None:
            assert r["ttftMinMs"] <= r["ttftMedianMs"] <= r["ttftMaxMs"]
    assert sum(r["errors"] for r in by_model.values()) >= 1
    too_many = await client.post("/api/admin/diagnostics/bedrock-latency", json={"runs": 6}, headers=headers)
    assert too_many.status_code == 422


async def test_unhandled_errors_keep_security_headers(
    client: httpx.AsyncClient, make_token: TokenFactory, graph_mock: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vanimo.graph import metadata

    async def boom(_: object) -> dict:
        raise RuntimeError("contains CANARY-ERR-content")

    _mock_profile(graph_mock)
    monkeypatch.setattr(metadata, "me", boom)
    resp = await client.get("/api/me", headers=_auth(make_token))
    assert resp.status_code == 500 and resp.json() == {"error": "internal"}
    assert resp.headers["X-Content-Type-Options"] == "nosniff" and resp.headers["X-Request-Id"]
    assert "CANARY-ERR" not in resp.text


async def test_database_outage_is_503_with_retry_after(
    settings: Settings, make_token: TokenFactory, graph_mock: respx.MockRouter
) -> None:
    from vanimo.main import create_app

    broken = settings.model_copy(
        update={
            "database_url": SecretStr("postgresql+psycopg://vanimo_app:x@127.0.0.1:1/vanimo"),
            "db_connect_timeout_s": 2,
        }
    )
    http = httpx.AsyncClient()
    state = AppState(
        settings=broken,
        engine=make_engine(broken),
        http=http,
        validator=TokenValidator(broken, JwksCache(broken.entra_jwks_url, http)),
        router=ModelRouter(broken),
        obo=FakeObo(),  # type: ignore[arg-type]
    )
    app = create_app(broken, state)
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app), httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        resp = await c.get("/api/me", headers=_auth(make_token))
    assert resp.status_code == 503 and resp.json() == {"error": "db_unavailable"}
    assert resp.headers["Retry-After"] == "15"
