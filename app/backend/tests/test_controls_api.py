"""M1 end to end on the sample workspace: scan → review → exclude → never-send → admin scoping."""

from __future__ import annotations

import httpx
import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import log_lines
from tests.helpers import _find, _settle, _sources, _user
from vanimo import canary
from vanimo.config import Settings
from vanimo.state import AppState

pytestmark = pytest.mark.db


async def test_scan_builds_the_sources_index(client: httpx.AsyncClient, scanned: dict) -> None:
    status = (await client.get("/api/controls/status", headers=scanned)).json()
    assert status["onboardingState"] == "review_pending"
    counts = status["scan"]["counts"]
    assert counts["people"] >= 60 and counts["chats"] == 13 and counts["messages"] >= 40 and counts["meetings"] >= 10
    assert status["scan"]["sourceKind"] == "sample"

    people = await _sources(client, scanned, "people")
    meera = _find(people, "Meera Iyer")
    assert meera["counts"]["emails"] > 0 and meera["counts"]["chats"] > 0 and not meera["excluded"]
    assert "personal email" in _find(people, "Nisha (home)")["flags"]
    chats = await _sources(client, scanned, "chats")
    assert "hidden in Teams" in _find(chats, "Old Acme pilot")["flags"]
    assert "large group" in _find(chats, "All Kestrel India")["flags"]
    assert any(c["label"].startswith("Rahul Verma, Priya Nair") for c in chats)  # unnamed chat label
    meetings = await _sources(client, scanned, "meetings")
    assert _find(meetings, "Acme weekly sync")["kind"] == "series"
    assert "private" in _find(meetings, "Doctor appointment")["flags"]
    domains = await _sources(client, scanned, "domains")
    assert "your organisation" in _find(domains, "kestrel.example")["flags"]


async def test_exclude_person_with_impact_and_untick(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState
) -> None:
    people = await _sources(client, scanned, "people")
    rahul = _find(people, "Rahul Verma")
    impact = (
        await client.post("/api/controls/impact", json={"kind": "person", "id": rahul["id"]}, headers=scanned)
    ).json()
    assert impact["emails"] > 0 and impact["threads"] > 0 and impact["chats"] >= 4
    big = next(c for c in impact["chatList"] if c["label"] == "All Kestrel India")
    assert big["large"] and impact["chatList"][0]["large"]  # large chats listed first for unticking

    rule = await client.post(
        "/api/controls/rules",
        json={"kind": "person", "id": rahul["id"], "exceptChatIds": [big["id"]]},
        headers=scanned,
    )
    assert rule.status_code == 201, rule.text
    assert rule.json()["label"] == "Rahul Verma" and rule.json()["exceptions"] == 1
    await _settle(app_state)

    people = await _sources(client, scanned, "people")
    assert _find(people, "Rahul Verma")["excluded"] and _find(people, "Rahul Verma")["ruleId"]
    chats = await _sources(client, scanned, "chats")
    assert _find(chats, "Rahul Verma")["excluded"] and _find(chats, "Rahul Verma")["via"] == ["Rahul Verma"]
    assert not _find(chats, "All Kestrel India")["excluded"]  # unticked
    threads = await _sources(client, scanned, "threads")
    assert next(t for t in threads if t["label"].endswith("Please prepare the UAT checklist"))["excluded"]

    again = await client.post("/api/controls/rules", json={"kind": "person", "id": rahul["id"]}, headers=scanned)
    assert again.status_code == 409

    receipts = (await client.get("/api/controls/receipts", headers=scanned)).json()
    assert receipts[0]["reason"] == "exclusion_added" and receipts[0]["status"] == "done"

    assert (await client.delete(f"/api/controls/rules/{rule.json()['id']}", headers=scanned)).status_code == 204
    await _settle(app_state)
    assert not _find(await _sources(client, scanned, "people"), "Rahul Verma")["excluded"]


async def test_exclude_thread_chat_meeting_series_and_domain(client: httpx.AsyncClient, scanned: dict) -> None:
    for kind, source_kind, label in [
        ("thread", "threads", "Re: Weekend plans"),
        ("chat", "chats", "Monsoon pricing (confidential)"),
        ("meeting", "meetings", "Doctor appointment"),
        ("series", "meetings", "Acme weekly sync"),
        ("domain", "domains", "gmail.com"),
    ]:
        item = _find(await _sources(client, scanned, source_kind), label)
        resp = await client.post("/api/controls/rules", json={"kind": kind, "id": item["id"]}, headers=scanned)
        assert resp.status_code == 201, (kind, resp.text)
        assert _find(await _sources(client, scanned, source_kind), label)["excluded"], kind
    rules = (await client.get("/api/controls/rules", headers=scanned)).json()
    assert {r["kind"] for r in rules} == {"thread", "chat", "meeting", "series", "domain"}
    # The domain rule makes the personal contact excluded too.
    assert _find(await _sources(client, scanned, "people"), "Nisha (home)")["excluded"]


async def test_never_send_words_are_scrubbed_from_the_index(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState, database: dict[str, str]
) -> None:
    preview = await client.post("/api/controls/never-send/preview", json={"text": "Falcon", "kind": "codename"},
                                headers=scanned)  # fmt: skip
    assert preview.status_code == 200
    assert preview.json()["appearsIn"] >= 4 and "falcon" in preview.json()["variants"]
    assert (await client.post("/api/controls/never-send/preview", json={"text": "Team"}, headers=scanned)).json()[
        "commonWord"
    ]

    added = await client.post("/api/controls/never-send", json={"text": "Falcon", "kind": "codename"}, headers=scanned)
    assert added.status_code == 201
    await _settle(app_state)
    threads = await _sources(client, scanned, "threads")
    assert not any("falcon" in t["label"].lower() for t in threads)
    assert any(t["label"].endswith("Project [removed] timeline") for t in threads)
    chats = await _sources(client, scanned, "chats")
    assert any(c["label"] == "[removed] war room" for c in chats)
    receipts = (await client.get("/api/controls/receipts", headers=scanned)).json()
    assert receipts[0]["reason"] == "term_added" and receipts[0]["counts"]["index_fields_rescrubbed"] >= 4

    # A fresh scan masks before storing (not only the scrub).
    await client.post("/api/controls/scan", headers=scanned)
    assert not any("falcon" in t["label"].lower() for t in await _sources(client, scanned, "threads"))

    words = (await client.get("/api/controls/never-send", headers=scanned)).json()
    assert words[0]["text"] == "Falcon" and words[0]["allowInDrafts"] is False
    dup = await client.post("/api/controls/never-send", json={"text": "falcon"}, headers=scanned)
    assert dup.status_code == 409
    assert (await client.patch(f"/api/controls/never-send/{words[0]['id']}", json={"allowInDrafts": True},
                               headers=scanned)).status_code == 204  # fmt: skip
    assert (await client.delete(f"/api/controls/never-send/{words[0]['id']}", headers=scanned)).status_code == 204


async def test_never_send_words_never_stored_in_plaintext(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState, database: dict[str, str],
    capsys: pytest.CaptureFixture,
) -> None:  # fmt: skip
    marker = canary.new_canary("word")
    resp = await client.post("/api/controls/never-send", json={"text": marker, "kind": "codename"}, headers=scanned)
    assert resp.status_code == 201
    await _settle(app_state)
    assert canary.scan_database(database["owner"], [marker]) == {}  # encrypted at rest
    assert marker not in capsys.readouterr().out  # and never logged
    assert (await client.get("/api/controls/never-send", headers=scanned)).json()[0]["text"] == marker  # owner sees it


async def test_review_gate(client: httpx.AsyncClient, database: dict[str, str], settings: Settings) -> None:
    h = await _user(client, database, settings)
    early = await client.post("/api/controls/review", json={"outcome": "finished"}, headers=h)
    assert early.status_code == 409 and early.json() == {"error": "scan_not_done"}
    await client.post("/api/controls/scan", headers=h)
    done = await client.post("/api/controls/review", json={"outcome": "finished"}, headers=h)
    assert done.status_code == 200 and done.json()["onboardingState"] == "review_done"
    assert (await client.get("/api/me", headers=h)).json()["onboardingState"] == "review_done"
    skipper = await _user(client, database, settings)
    skipped = await client.post("/api/controls/review", json={"outcome": "skipped"}, headers=skipper)
    assert skipped.json()["reviewOutcome"] == "skipped"


async def test_admin_client_scoping(
    client: httpx.AsyncClient, database: dict[str, str], settings: Settings, scanned: dict
) -> None:
    admin = await _user(client, database, settings, role="admin")
    # Users in the same (local) tenant: the admin's rules apply to the scanned user.
    assert (await client.get("/api/admin/scoping", headers=scanned)).status_code == 403
    resp = await client.post(
        "/api/admin/scoping/accounts",
        json={"name": "Bluefin Bank", "mode": "excluded", "domains": ["BluefinBank.example", "@bluefin.example"],
              "sensitiveWords": ["Falcon", "Falcon"]},
        headers=admin,
    )  # fmt: skip
    assert resp.status_code == 201, resp.text
    account = resp.json()["accounts"][0]
    assert account["domains"] == ["bluefin.example", "bluefinbank.example"] and account["sensitiveWords"] == 1

    people = await _sources(client, scanned, "people")
    karan = _find(people, "Karan Malhotra")
    assert karan["excluded"] and karan["locked"] and karan["via"] == ["Your organisation: Bluefin Bank"]
    deepa = _find(people, "Deepa Rao")  # subdomain cards.bluefinbank.example
    assert deepa["locked"]
    threads = await _sources(client, scanned, "threads")
    assert next(t for t in threads if t["label"].endswith("Project Falcon timeline"))["locked"]

    bad = await client.post("/api/admin/scoping/accounts", headers=admin,
                            json={"name": "x", "mode": "excluded", "domains": ["not a domain"]})  # fmt: skip
    assert bad.status_code == 422
    clash = await client.post("/api/admin/scoping/accounts", headers=admin,
                              json={"name": "y", "mode": "approved", "domains": ["bluefinbank.example"]})  # fmt: skip
    assert clash.status_code == 409

    # Approved-only: external people outside approved accounts are excluded; colleagues aren't.
    await client.post("/api/admin/scoping/accounts", headers=admin,
                      json={"name": "Acme Retail", "mode": "approved", "domains": ["acmeretail.example"]})  # fmt: skip
    mode = await client.put("/api/admin/scoping/policy", json={"externalMode": "approved_only"}, headers=admin)
    assert mode.json()["externalMode"] == "approved_only"
    people = await _sources(client, scanned, "people")
    assert _find(people, "Emily Park")["locked"]  # Orion Health: not approved
    assert not _find(people, "John Miller")["excluded"]  # Acme: approved
    assert not _find(people, "Meera Iyer")["excluded"]  # internal

    await client.put("/api/admin/scoping/policy", json={"externalMode": "allow_all"}, headers=admin)
    removed = await client.delete(f"/api/admin/scoping/accounts/{account['id']}", headers=admin)
    assert removed.status_code == 200
    assert not _find(await _sources(client, scanned, "people"), "Karan Malhotra")["excluded"]
    # Leave the shared local tenant as we found it.
    for left in removed.json()["accounts"]:
        await client.delete(f"/api/admin/scoping/accounts/{left['id']}", headers=admin)


async def test_database_refuses_org_writes_outside_admin_transactions(database: dict[str, str]) -> None:
    engine = create_async_engine(database["app"])
    with psycopg.connect(database["owner"].replace("postgresql+psycopg://", "postgresql://")) as conn:
        tenant, user = conn.execute(
            "select u.tenant_id, u.id from vanimo.users u join vanimo.tenants t on t.id = u.tenant_id "
            "where t.entra_tenant_id = 'local' limit 1"
        ).fetchone()
    from vanimo.db.session import UserRef, user_tx

    ref = UserRef(tenant, user)
    with pytest.raises(DBAPIError, match="row-level security"):
        async with user_tx(engine, ref) as c:
            await c.execute(
                text("insert into vanimo.tenant_policies (tenant_id, external_mode) values (:t, 'approved_only')"),
                {"t": tenant},
            )
    async with user_tx(engine, ref, admin=True) as c:  # the API sets this only after its role check
        await c.execute(
            text("insert into vanimo.tenant_policies (tenant_id) values (:t) on conflict do nothing"), {"t": tenant}
        )
    await engine.dispose()


async def test_users_cannot_touch_each_others_sources(
    client: httpx.AsyncClient, database: dict[str, str], settings: Settings, scanned: dict
) -> None:
    other = await _user(client, database, settings)
    await client.post("/api/controls/scan", headers=other)
    mine = _find(await _sources(client, scanned, "people"), "Meera Iyer")
    theirs = _find(await _sources(client, other, "people"), "Meera Iyer")
    assert mine["id"] != theirs["id"]
    # Using someone else's index row ID finds nothing (row-level security), so no rule is created.
    resp = await client.post("/api/controls/rules", json={"kind": "person", "id": mine["id"]}, headers=other)
    assert resp.status_code == 404
    assert (await client.get("/api/controls/rules", headers=other)).json() == []


async def test_controls_logs_are_content_free(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState, capsys: pytest.CaptureFixture
) -> None:
    people = await _sources(client, scanned, "people")
    await client.post("/api/controls/rules", json={"kind": "person", "id": _find(people, "Karan Malhotra")["id"]},
                      headers=scanned)  # fmt: skip
    await client.post("/api/controls/never-send", json={"text": "Monsoon"}, headers=scanned)
    await _settle(app_state)
    out = capsys.readouterr().out
    for secret in ("Karan", "bluefin", "Monsoon", "Meera", "Falcon"):
        assert secret.lower() not in out.lower()
    assert any(line.get("event") == "controls.rule_added" for line in log_lines(out))
