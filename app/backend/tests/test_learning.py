"""M2 end to end on the sample workspace: gate → learn → what's stored → persona → purges."""

from __future__ import annotations

import httpx
import psycopg
import pytest

from tests.helpers import _find, _settle, _sources, _user
from vanimo.config import Settings
from vanimo.state import AppState

PLANTED = [
    "2341 2341 2346",
    "ABCPE1234F",
    "27AAPFU0939F1ZV",
    "50100234567891",
    "HDFC0001234",
    "resort.booking@okaxis",
    "98765 43210",
    "4111 1111 1111 1111",
    "AKIAIOSFODNN7EXAMPLE",
    "Kestrel@2026",
    "536-22-1847",
    "021000021",
]


async def _review(client: httpx.AsyncClient, h: dict) -> None:
    resp = await client.post("/api/controls/review", json={"outcome": "finished"}, headers=h)
    assert resp.status_code == 200, resp.text


async def _learn(client: httpx.AsyncClient, h: dict) -> dict:
    resp = await client.post("/api/learning/run", headers=h)
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["run"]["status"] == "done", body
    return body


async def _items(client: httpx.AsyncClient, h: dict) -> list[dict]:
    resp = await client.get("/api/learning/items", params={"limit": 200}, headers=h)
    assert resp.status_code == 200, resp.text
    return resp.json()["items"]


def _owner_dump(database: dict[str, str]) -> str:
    """Every stored learning row as text, read as the table owner (bypassing the API)."""
    url = database["owner"].replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url) as conn:
        rows = []
        for table in (
            "l1_items",
            "l1_tokens",
            "style_cards",
            "learning_runs",
            "eval_runs",
            "persona_settings",
            "conversation_tones",
        ):
            rows += [str(r) for r in conn.execute(f"select * from vanimo.{table}").fetchall()]  # noqa: S608
    return "\n".join(rows)


async def test_learning_needs_the_review(client: httpx.AsyncClient, scanned: dict) -> None:
    resp = await client.post("/api/learning/run", headers=scanned)
    assert resp.status_code == 409 and resp.json() == {"error": "review_pending"}
    status = (await client.get("/api/learning", headers=scanned)).json()
    assert status["run"] is None and status["stored"]["total"] == 0


async def test_learn_store_persona_and_purges(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState, database: dict[str, str]
) -> None:
    h = scanned
    assert (
        await client.post("/api/controls/never-send", json={"text": "Falcon", "kind": "codename"}, headers=h)
    ).status_code == 201
    await _settle(app_state)
    await _review(client, h)
    body = await _learn(client, h)
    counts = body["run"]["counts"]
    assert body["stored"]["email"] >= 30 and body["stored"]["chat"] >= 10
    assert counts.get("email_excluded", 0) == 0 and body["styleCards"] >= 5
    assert not any(k.startswith("blocked") for k in counts), counts

    # What was stored: no regulated value, secret, never-send word or raw address; names are tokens.
    items = await _items(client, h)
    stored = "\n".join(i["stored"] + "\n" + (i["contextStored"] or "") + "\n" + (i["subject"] or "") for i in items)
    for value in [*PLANTED, "Falcon", "falcon", "kestrel.example", "Meera", "Siddharth"]:
        assert value not in stored, value
    assert "⟦ME.full⟧" in stored and "[PAN]" in stored and "⟦NS_" in stored
    display = "\n".join(i["display"] for i in items)
    assert "Meera" in display and "[removed]" in display and "[Aadhaar number]" in display
    assert "Falcon" not in display and "⟦" not in display

    # At rest: everything encrypted; nothing planted or never-send readable even to the table owner.
    dump = _owner_dump(database)
    for value in [*PLANTED, "Falcon", "Meera Iyer", "Best regards"]:
        assert value not in dump, value

    # Persona Snapshot (F15): tone groups from how the user writes, not from job titles.
    persona = (await client.get("/api/persona", headers=h)).json()
    assert persona["learned_items"] == body["stored"]["total"]
    tone_of = {(c["bucket"], c["label"]): c for c in persona["conversations"]}
    assert tone_of[("email", "Karan Malhotra")]["tone"] == "formal"  # a client: Dear …, Kindly, Best regards
    assert tone_of[("email", "Meera Iyer")]["tone"] == "friendly"  # the manager: Hi Meera … Thanks
    assert tone_of[("email", "Arjun Mehta")]["tone"] == "casual"  # a peer and friend: Hey Arjun … Cheers
    assert tone_of[("dm", "Rahul Verma")]["tone"] == "casual"  # Hinglish in chat with a report
    assert tone_of[("dm", "Vikram Shah")]["tone"] == "casual"  # "thanks yaar"
    assert tone_of[("email", "Karan Malhotra")]["basis"] == "your_messages" and "Karan" not in str(
        _owner_dump(database)
    )
    cards = persona["tone_bucket_cards"]
    assert cards["formal|email"]["greetings"][0][0] == "Dear {first},"
    assert any("{me_full}" in s for s, _ in cards["formal|email"]["sign_offs"])
    assert cards["friendly|email"]["sign_offs"][0][0] == "Thanks,\n{me}"
    assert cards["casual|dm"]["greetings"][0][0] == "(none)"  # no greeting in a casual chat
    assert "pfa" in persona["overall"]["keep_list"] or "kindly" in persona["overall"]["keep_list"]
    formal_words = [p["phrase"] for ps in persona["vocabulary"]["tones"]["formal"].values() for p in ps]
    assert "kindly revert" in formal_words  # used with three different clients
    assert all(p["conversations"] >= 3 for ps in persona["vocabulary"]["tones"]["formal"].values() for p in ps)
    assert persona["by"]["language"].get("hinglish", 0) >= 3 and persona["by"]["bucket"]["dm"] >= 5
    assert persona["evaluation"]["metrics"]["n_eval"] >= 1

    # The user's own choice of tone wins, moves that conversation's messages, and survives learning again.
    meera = tone_of[("email", "Meera Iyer")]
    chosen = await client.put(
        "/api/persona/tones", json={"bucket": "email", "key": meera["key"], "tone": "formal"}, headers=h
    )
    assert chosen.status_code == 204
    after_choice = {
        (c["bucket"], c["label"]): c for c in (await client.get("/api/persona", headers=h)).json()["conversations"]
    }
    assert after_choice[("email", "Meera Iyer")]["tone"] == "formal"
    assert after_choice[("email", "Meera Iyer")]["judged"] == "friendly"
    bad = await client.put("/api/persona/tones", json={"bucket": "dm", "key": "0" * 64, "tone": "casual"}, headers=h)
    assert bad.status_code == 404

    saved = await client.put(
        "/api/persona/settings",
        headers=h,
        json={
            "formality": 1,
            "phrases_do": ["Project Falcon update", "Cheers"],
            "phrases_dont": ["Hope this finds you well"],
        },
    )
    assert saved.status_code == 200 and saved.json()["phrases_do"][0].startswith("Project ⟦NS_")
    assert "Falcon" not in saved.json()["phrases_do"][0]

    # Sample workspace: Outlook-style view with what happened to each item.
    ws = (await client.get("/api/sample/workspace", headers=h)).json()
    statuses = {e["status"] for e in ws["emails"]}
    assert {"learned", "received"} <= statuses
    learned = next(e for e in ws["emails"] if e["status"] == "learned")
    one = await client.get("/api/learning/items", params={"ids": [learned["storedId"]]}, headers=h)
    assert one.json()["total"] == 1

    # Exclude a client contact: everything learned with him is purged by the job, with a receipt.
    people = await _sources(client, h, "people")
    john = _find(people, "John Miller")
    with_john = sum(
        1
        for e in ws["emails"]
        if e["status"] == "learned" and any(p["email"].startswith("john.miller@") for p in e["to"] + e["cc"])
    )
    assert with_john >= 3
    assert (
        await client.post("/api/controls/rules", json={"kind": "person", "id": john["id"]}, headers=h)
    ).status_code == 201
    await _settle(app_state)
    receipts = (await client.get("/api/controls/receipts", headers=h)).json()
    purge = next(r for r in receipts if r["reason"] == "exclusion_added")
    assert purge["status"] == "done" and purge["counts"]["l1_items_deleted"] >= with_john
    ws = (await client.get("/api/sample/workspace", headers=h)).json()
    for e in ws["emails"]:
        if e["direction"] == "sent" and any(p["email"].startswith("john.miller@") for p in e["to"] + e["cc"]):
            assert e["status"] == "excluded" and e["storedId"] is None
    after = (await client.get("/api/learning", headers=h)).json()
    assert after["stored"]["total"] == body["stored"]["total"] - purge["counts"]["l1_items_deleted"]
    # His tone went with him (F15); everyone else's stayed.
    labels = {(c["bucket"], c["label"]) for c in (await client.get("/api/persona", headers=h)).json()["conversations"]}
    assert ("email", "John Miller") not in labels and ("email", "Karan Malhotra") in labels
    assert purge["counts"]["tones_deleted"] >= 1

    # A never-send word added after learning disappears from stored history too.
    assert any("Monsoon" in i["display"] for i in await _items(client, h))
    assert (await client.post("/api/controls/never-send", json={"text": "Monsoon"}, headers=h)).status_code == 201
    await _settle(app_state)
    assert not any("Monsoon" in i["display"] or "Monsoon" in i["stored"] for i in await _items(client, h))

    # Learning again respects the new rules (John stays out) and the user's choices — and runs can't overlap.
    again = await _learn(client, h)
    assert again["stored"]["total"] == after["stored"]["total"] and again["learned"]
    relearned = {
        (c["bucket"], c["label"]): c for c in (await client.get("/api/persona", headers=h)).json()["conversations"]
    }
    assert relearned[("email", "Meera Iyer")]["override"] == "formal"
    assert ("email", "John Miller") not in relearned

    # Delete everything learned: receipt, nothing left, and drafting waits for learning again.
    deleted = await client.delete("/api/learning", headers=h)
    assert deleted.status_code == 200 and deleted.json()["status"] == "done"
    assert deleted.json()["counts"]["l1_items_deleted"] == again["stored"]["total"]
    status = (await client.get("/api/learning", headers=h)).json()
    assert status["stored"]["total"] == 0 and status["styleCards"] == 0 and not status["learned"]
    assert (await client.get("/api/persona", headers=h)).json()["conversations"] == []


async def test_admin_client_exclusion_purges_learned_data(
    client: httpx.AsyncClient,
    scanned: dict,
    app_state: AppState,
    database: dict[str, str],
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    h = scanned
    await _review(client, h)
    body = await _learn(client, h)
    admin = await _user(client, database, settings, role="admin")
    resp = await client.post(
        "/api/admin/scoping/accounts",
        headers=admin,
        json={"name": "Acme Retail", "mode": "excluded", "domains": ["acmeretail.example"]},
    )
    assert resp.status_code == 201, resp.text
    account_id = resp.json()["accounts"][0]["id"]
    try:
        await _settle(app_state)  # the purge starts right after the admin change (no sweeper wait)
        receipts = (await client.get("/api/controls/receipts", headers=h)).json()
        job = next(r for r in receipts if r["reason"] == "tenant_policy_changed")
        assert job["status"] == "done" and job["counts"]["l1_items_deleted"] >= 5
        stored = (await client.get("/api/learning", headers=h)).json()["stored"]["total"]
        assert stored == body["stored"]["total"] - job["counts"]["l1_items_deleted"]
        ws = (await client.get("/api/sample/workspace", headers=h)).json()
        acme = [e for e in ws["emails"] if e["direction"] == "sent" and "Acme" in (e["subject"] or "")]
        assert acme and all(e["status"] == "excluded" and "client_account" in e["reasons"] for e in acme)
    finally:
        await client.delete(f"/api/admin/scoping/accounts/{account_id}", headers=admin)


async def test_controls_change_mid_run_restarts(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rule or word added while the run reads wins: persist sees the version change, the run
    re-collects with the new controls."""
    from vanimo.controls.store import bump_version
    from vanimo.db.session import user_tx
    from vanimo.learning import backfill

    await _review(client, scanned)
    calls = {"collect": 0, "persist": 0}
    real_collect, real_persist = backfill.collect, backfill.persist

    async def counting_collect(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls["collect"] += 1
        return await real_collect(*args, **kwargs)

    async def change_then_persist(engine, vault, ref, *args, **kwargs):  # type: ignore[no-untyped-def]
        calls["persist"] += 1
        if calls["persist"] == 1:  # someone adds a rule between reading and storing
            async with user_tx(engine, ref) as conn:
                await bump_version(conn, ref)
        return await real_persist(engine, vault, ref, *args, **kwargs)

    monkeypatch.setattr(backfill, "collect", counting_collect)
    monkeypatch.setattr(backfill, "persist", change_then_persist)
    body = await _learn(client, scanned)
    assert calls == {"collect": 2, "persist": 2} and body["stored"]["total"] > 0
