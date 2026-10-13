from __future__ import annotations

import httpx
import pytest
import respx

from vanimo.graph import client as graph_client
from vanimo.graph import metadata
from vanimo.graph.client import GraphClient, GraphError

GRAPH = "https://graph.microsoft.com/v1.0"


def test_metadata_field_lists_never_include_content() -> None:
    for fields in (metadata.SENT_HEADER_FIELDS, metadata.ME_FIELDS, metadata.MANAGER_FIELDS):
        metadata.assert_metadata_only(fields)
    with pytest.raises(ValueError, match="content fields"):
        metadata.assert_metadata_only(("id", "uniqueBody"))
    with pytest.raises(ValueError):
        metadata.assert_metadata_only(["subject", "bodyPreview"])


async def test_retries_throttling_with_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(s: float) -> None:
        sleeps.append(s)

    monkeypatch.setattr(graph_client.asyncio, "sleep", fake_sleep)
    with respx.mock() as router:
        route = router.get(f"{GRAPH}/me").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "7"}),
                httpx.Response(503),
                httpx.Response(200, json={"id": "1"}),
            ]
        )
        g = GraphClient("t", httpx.AsyncClient())
        assert await g.get("me") == {"id": "1"}
    assert route.call_count == 3
    assert sleeps[0] == 7 and 1 <= sleeps[1] <= 2.5


async def test_gives_up_after_max_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(graph_client.asyncio, "sleep", no_sleep)
    with respx.mock() as router:
        router.get(f"{GRAPH}/me").mock(return_value=httpx.Response(429, json={"error": {"code": "TooManyRequests"}}))
        with pytest.raises(GraphError) as exc:
            await GraphClient("t", httpx.AsyncClient(), max_attempts=3).get("me")
    assert exc.value.status == 429 and exc.value.code == "TooManyRequests"


async def test_error_code_sanitised() -> None:
    with respx.mock() as router:
        router.get(f"{GRAPH}/me").mock(
            return_value=httpx.Response(400, json={"error": {"code": "Bad <script> priya@x.com"}})
        )
        with pytest.raises(GraphError) as exc:
            await GraphClient("t", httpx.AsyncClient()).get("me")
    assert exc.value.code == "unknown"


async def test_refuses_non_graph_urls() -> None:
    g = GraphClient("t", httpx.AsyncClient())
    with pytest.raises(ValueError):
        await g.get("https://evil.example.com/steal")


async def test_pagination_follows_next_link() -> None:
    with respx.mock() as router:
        # Routes match in order; the more specific one goes first.
        router.get(f"{GRAPH}/me/chats", params={"skip": "1"}).mock(
            return_value=httpx.Response(200, json={"value": [2]})
        )
        router.get(f"{GRAPH}/me/chats").mock(
            return_value=httpx.Response(200, json={"value": [1], "@odata.nextLink": f"{GRAPH}/me/chats?skip=1"})
        )
        pages = [p async for p in GraphClient("t", httpx.AsyncClient()).pages("me/chats")]
    assert [p["value"] for p in pages] == [[1], [2]]
