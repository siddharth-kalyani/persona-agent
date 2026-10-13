"""End-to-end API tests with a mocked Microsoft Graph and a real (local) Postgres."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from tests.conftest import TokenFactory, log_lines

pytestmark = pytest.mark.db
GRAPH = "https://graph.microsoft.com/v1.0"
CANARY_SUBJECT = "CANARY-SUBJ-7f3a Project Falcon pricing"


def _mock_profile(graph_mock: respx.MockRouter) -> respx.Route:
    graph_mock.get(f"{GRAPH}/me").mock(
        return_value=httpx.Response(200, json={"id": "x", "displayName": "Asha Rao", "jobTitle": "Consultant"})
    )
    graph_mock.get(f"{GRAPH}/me/manager").mock(
        return_value=httpx.Response(200, json={"id": "y", "displayName": "Vikram Shah", "jobTitle": "Director"})
    )
    return graph_mock.get(f"{GRAPH}/me/mailFolders/sentitems/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "m1",
                        "subject": CANARY_SUBJECT,
                        "sentDateTime": "2026-10-12T10:00:00Z",
                        "toRecipients": [{"emailAddress": {"address": "a@example.com"}}],
                        "ccRecipients": [],
                    },
                    {
                        "id": "m2",
                        "subject": "Re: SOW",
                        "sentDateTime": "2026-10-11T09:00:00Z",
                        "toRecipients": [],
                        "ccRecipients": [{}, {}],
                        "bccRecipients": [{}],
                    },
                ]
            },
        )
    )


async def test_me_happy_path(
    client: httpx.AsyncClient, make_token: TokenFactory, graph_mock: respx.MockRouter, capsys: pytest.CaptureFixture
) -> None:
    sent_route = _mock_profile(graph_mock)
    resp = await client.get("/api/me", headers={"Authorization": f"Bearer {make_token()}"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["displayName"] == "Asha Rao"
    assert body["manager"]["displayName"] == "Vikram Shah"
    assert [m["recipientCount"] for m in body["recentSent"]] == [1, 3]
    assert body["onboardingState"] == "review_pending"
    assert body["roles"] == ["Vanimo.User"]
    assert resp.headers["X-Content-Type-Options"] == "nosniff"

    # Only header fields were requested — never a body.
    select = sent_route.calls.last.request.url.params["$select"]
    assert "body" not in select.lower() and "preview" not in select.lower()
    assert sent_route.calls.last.request.headers["Authorization"].startswith("Bearer graph-token-for-")

    # Content-free logs: neither the subject nor any person's name reaches a log line.
    out = capsys.readouterr().out
    for secret in (CANARY_SUBJECT, "CANARY-SUBJ", "Asha", "Vikram", "a@example.com"):
        assert secret not in out
    access = [line for line in log_lines(out) if line.get("event") == "http.request"]
    assert access and access[-1]["route"] == "/api/me" and access[-1]["status"] == 200


async def test_me_without_manager(
    client: httpx.AsyncClient, make_token: TokenFactory, graph_mock: respx.MockRouter
) -> None:
    _mock_profile(graph_mock)
    graph_mock.get(f"{GRAPH}/me/manager").mock(
        return_value=httpx.Response(404, json={"error": {"code": "Request_ResourceNotFound"}})
    )
    resp = await client.get("/api/me", headers={"Authorization": f"Bearer {make_token()}"})
    assert resp.status_code == 200
    assert resp.json()["manager"] is None


async def test_me_requires_token(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/me")
    assert resp.status_code == 401
    assert resp.json() == {"error": "missing_token"}
    assert "missing_token" in resp.headers["WWW-Authenticate"]


async def test_graph_error_is_reported_without_content(
    client: httpx.AsyncClient, make_token: TokenFactory, graph_mock: respx.MockRouter
) -> None:
    _mock_profile(graph_mock)
    graph_mock.get(f"{GRAPH}/me").mock(
        return_value=httpx.Response(403, json={"error": {"code": "ErrorAccessDenied", "message": "secret text"}})
    )
    resp = await client.get("/api/me", headers={"Authorization": f"Bearer {make_token()}"})
    assert resp.status_code == 403
    assert resp.json() == {"error": "graph_error", "graphStatus": 403, "graphCode": "ErrorAccessDenied"}


async def test_validation_errors_do_not_echo_input(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    resp = await client.post(
        "/api/admin/diagnostics/bedrock-latency",
        headers={"Authorization": f"Bearer {make_token(roles=('Vanimo.Admin',))}"},
        json={"runs": "CANARY-INPUT-91"},
    )
    assert resp.status_code == 422
    assert "CANARY-INPUT-91" not in resp.text


async def test_diagnostics_require_admin(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    resp = await client.post("/api/admin/diagnostics/run", json={}, headers={"Authorization": f"Bearer {make_token()}"})
    assert resp.status_code == 403
    assert resp.json() == {"error": "admin_role_required"}


async def test_diagnostics_run_is_content_free(
    client: httpx.AsyncClient, make_token: TokenFactory, graph_mock: respx.MockRouter
) -> None:
    _mock_profile(graph_mock)
    graph_mock.get(f"{GRAPH}/me/mailFolders/sentitems/messages/delta").mock(
        return_value=httpx.Response(
            200, json={"value": [{"id": "1", "subject": CANARY_SUBJECT}], "@odata.deltaLink": f"{GRAPH}/delta?token=x"}
        )
    )
    graph_mock.get(f"{GRAPH}/me/chats").mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {"id": "c1", "chatType": "group", "topic": CANARY_SUBJECT, "members": [{}, {}, {}]},
                    {"id": "c2", "chatType": "oneOnOne", "topic": None, "members": [{}, {}]},
                ]
            },
        )
    )
    graph_mock.get(f"{GRAPH}/me/calendarView").mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "e1",
                        "isOnlineMeeting": True,
                        "isOrganizer": False,
                        "onlineMeeting": {"joinUrl": "https://teams.microsoft.com/l/meetup-join/abc"},
                    },
                ]
            },
        )
    )
    graph_mock.get(f"{GRAPH}/me/onlineMeetings").mock(return_value=httpx.Response(200, json={"value": [{"id": "om1"}]}))
    graph_mock.get(f"{GRAPH}/me/onlineMeetings/om1/transcripts").mock(
        return_value=httpx.Response(403, json={"error": {"code": "Forbidden"}})
    )
    resp = await client.post(
        "/api/admin/diagnostics/run",
        json={},
        headers={"Authorization": f"Bearer {make_token(roles=('Vanimo.Admin',))}"},
    )
    assert resp.status_code == 200, resp.text
    results = {r["check"]: r for r in resp.json()["results"]}
    assert results["chats_roster"]["details"]["type_group"] == 1
    assert results["chats_roster"]["details"]["max_members"] == 3
    assert results["sent_delta_headers"]["details"]["reached_delta_link_in_3_pages"] is True
    assert results["meeting_transcripts"]["outcome"] == "warn"
    assert results["meeting_transcripts"]["details"]["attendee_error"] == 1
    assert "unique_body_in_delta" not in results  # body probe is opt-in only
    assert CANARY_SUBJECT not in resp.text
    assert "abc" not in json.dumps(results["meeting_transcripts"])


async def test_draft_probe_delete_refuses_unknown_drafts(
    client: httpx.AsyncClient, make_token: TokenFactory, graph_mock: respx.MockRouter
) -> None:
    delete_route = graph_mock.delete(url__regex=rf"{GRAPH}/me/messages/.*").mock(return_value=httpx.Response(204))
    headers = {"Authorization": f"Bearer {make_token(roles=('Vanimo.Admin',))}"}
    resp = await client.delete("/api/admin/diagnostics/draft-probe/AAMkSomeoneElsesMail", headers=headers)
    assert resp.status_code == 404
    resp = await client.delete("/api/admin/diagnostics/draft-probe/..%2F..%2Fme", headers=headers)
    assert resp.status_code in (404, 422)
    assert not delete_route.called


async def test_draft_probe_roundtrip(
    client: httpx.AsyncClient, make_token: TokenFactory, graph_mock: respx.MockRouter
) -> None:
    oid = "44444444-4444-4444-4444-444444444444"
    headers = {"Authorization": f"Bearer {make_token(oid=oid, roles=('Vanimo.Admin',))}"}
    graph_mock.get(f"{GRAPH}/me/mailFolders/inbox/messages").mock(
        return_value=httpx.Response(200, json={"value": [{"id": "INBOX1"}]})
    )
    create = graph_mock.post(f"{GRAPH}/me/messages/INBOX1/createReply").mock(
        return_value=httpx.Response(201, json={"id": "DRAFT_1=", "webLink": "https://outlook.office.com/x"})
    )
    delete = graph_mock.delete(f"{GRAPH}/me/messages/DRAFT_1=").mock(return_value=httpx.Response(204))
    resp = await client.post("/api/admin/diagnostics/draft-probe", headers=headers)
    assert resp.status_code == 200 and resp.json()["draftId"] == "DRAFT_1="
    assert "safe to delete" in json.loads(create.calls.last.request.content)["comment"]

    # A different admin cannot delete it (their audit log has no record of it).
    other = {"Authorization": f"Bearer {make_token(roles=('Vanimo.Admin',))}"}
    assert (await client.delete("/api/admin/diagnostics/draft-probe/DRAFT_1=", headers=other)).status_code == 404
    assert (await client.delete("/api/admin/diagnostics/draft-probe/DRAFT_1=", headers=headers)).status_code == 204
    assert delete.call_count == 1


async def test_health(client: httpx.AsyncClient) -> None:
    assert (await client.get("/healthz")).json() == {"status": "ok"}
    assert (await client.get("/readyz")).json() == {"status": "ready"}
