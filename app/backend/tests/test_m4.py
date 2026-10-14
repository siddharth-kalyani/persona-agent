"""M4: drafts queue, drafts in the Outlook Drafts folder, draft↔sent matching and learned rules."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import psycopg
import pytest

from tests.helpers import _find, _settle, _sources, _user
from tests.test_drafting import _bedrock, _draft, _prompt, _ready, _thread_id
from vanimo.api import deps
from vanimo.config import Settings
from vanimo.drafting.prompt import Prompt, apply_rules
from vanimo.drafting.queue import AUTOMATED
from vanimo.edits import rules
from vanimo.edits.diff import compare
from vanimo.state import AppState

REPORT = {"email": "rahul.verma@kestrel.example", "name": "Rahul Verma"}


# --- units ----------------------------------------------------------------------------------------
def test_compare_outcomes_and_edits() -> None:
    d = (
        "Hi ⟦PERSON_aaaaaaaa⟧,\n\nThe build is ready. Please do not hesitate to reach out if you need anything!"
        "\n\nThanks,\n⟦ME⟧"
    )
    assert compare(d, d).outcome == "sent_as_is" and compare(d, d).edits == []
    s = "Hi ⟦PERSON_aaaaaaaa⟧,\n\nThe build is ready.\n\nThanks,\n⟦ME⟧"
    c = compare(d, s)
    kinds = {(e.kind, e.value) for e in c.edits}
    assert ("avoid", "please do not hesitate to reach out") in kinds and ("exclamations", "none") in kinds
    assert compare(d, "Lunch on Friday? I booked the usual place for noon.").outcome == "rewritten"
    # Dates are content, never a style preference; a never-send placeholder equals [removed] on screen.
    dates = compare("We deliver on Friday.", "We deliver on Monday.")
    assert [e.kind for e in dates.edits] == ["content"]
    assert compare("The ⟦NS_abcd1234⟧ plan is ready.", "The [removed] plan is ready.").outcome == "sent_as_is"


def test_rule_support_and_text() -> None:
    sent = ["Hi team,\nPls share the deck.\nThanks", "Pls review.\nThanks", "Pls check.\nThanks"]
    assert rules.support("prefer", "please -> pls", sent) == 1.0
    assert rules.support("avoid", "please do not hesitate", sent) == 1.0
    assert rules.support("exclamations", "none", sent) == 1.0
    assert rules.support("greeting", "Hi team,", sent[:2]) is None  # too few to judge
    assert rules.describe("prefer", "please -> pls") == 'Write "pls" instead of "please"'
    assert rules.describe("greeting", "(none)") == "No greeting"


def test_apply_rules_never_touches_tokens_or_slots() -> None:
    p = Prompt(system=[], user="", target_words=20, bounds=(5, 40), greeting="", sign_off="")
    p.prefer = [("please", "pls"), ("account", "a/c")]
    p.no_exclamations = True
    p.drop = ["do not hesitate"]
    body = "Please send the [bank account] details to ⟦PERSON_aaaaaaaa⟧! Do not hesitate to ask. The account is fine."
    out = apply_rules(body, p)
    assert out == "Pls send the [bank account] details to ⟦PERSON_aaaaaaaa⟧. The a/c is fine."


def test_automated_senders() -> None:
    for a in ("noreply@x.example", "no-reply+abc@x.example", "notifications@github.example", "do-not-reply@x.example"):
        assert AUTOMATED.match(a)
    assert not AUTOMATED.match("john.miller@acmeretail.example")


# --- queue and the Drafts folder ------------------------------------------------------------------
async def _queue(client: httpx.AsyncClient, h: dict) -> dict:
    resp = await client.get("/api/queue", headers=h)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_queue_and_outlook_drafts(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState, database: dict[str, str], settings: Settings
) -> None:
    h = scanned
    await _ready(client, h)
    q = await _queue(client, h)
    by_subject = {i["subject"]: i for i in q["items"]}
    q4 = by_subject["Q4 resource plan before Thursday"]
    assert q4["needsReply"] and q4["reason"] == "asks you to do something" and q4["draft"] is None
    assert by_subject["Acme go-live date?"]["needsReply"]
    assert q["settings"] == {"outlookDrafts": False, "staleDays": 3, "allowedByOrganisation": True}

    # Off by default: the draft is made, not placed.
    prep = (await client.post("/api/queue/prepare", json={"conversationId": q4["conversationId"]}, headers=h)).json()
    assert prep["placed"] is False and prep["notPlacedReason"] == "off" and prep["draft"]["id"]

    assert (
        await client.put("/api/drafting/settings", json={"outlookDrafts": True, "staleDays": 1}, headers=h)
    ).status_code == 200
    acme = by_subject["Acme go-live date?"]
    prep = (await client.post("/api/queue/prepare", json={"conversationId": acme["conversationId"]}, headers=h)).json()
    assert prep["placed"] is True
    q = await _queue(client, h)
    assert next(i for i in q["items"] if i["conversationId"] == acme["conversationId"])["draft"]["placed"]

    # A draft with a blocking check never goes to the mailbox without the user's confirmation.
    bec = by_subject["Updated bank details for CloudNest invoice"]
    prep = (await client.post("/api/queue/prepare", json={"conversationId": bec["conversationId"]}, headers=h)).json()
    assert prep["placed"] is False and prep["notPlacedReason"] == "blocked"
    draft_id = prep["draft"]["id"]
    refused = await client.post(f"/api/drafts/{draft_id}/place", json={"text": "Edited by me"}, headers=h)
    assert refused.status_code == 409 and refused.json()["error"] == "confirmation_required"
    ok = await client.post(f"/api/drafts/{draft_id}/place", json={"text": "Edited by me", "confirmed": True}, headers=h)
    assert ok.status_code == 200 and ok.json()["placed"]
    again = await client.post(f"/api/drafts/{draft_id}/place", json={"text": "x", "confirmed": True}, headers=h)
    assert again.json()["error"] == "already_placed"

    # Tidy: placed drafts older than the setting (1 day) and untouched are removed.
    url = database["owner"].replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url) as conn:
        conn.execute("update vanimo.drafts set placed_at = now() - interval '2 days' where placed_state = 'placed'")
    tidied = (await client.post("/api/queue/tidy", headers=h)).json()
    assert tidied == {"removed_stale": 2}

    # Dismiss: no longer listed.
    assert (
        await client.post("/api/queue/dismiss", json={"conversationId": q4["conversationId"]}, headers=h)
    ).status_code == 204
    assert all(i["conversationId"] != q4["conversationId"] for i in (await _queue(client, h))["items"])

    # The organisation can switch drafts in mailboxes off.
    admin = await _user(client, database, settings, role="admin")
    assert (await client.put("/api/admin/scoping/drafts", json={"serverDrafts": False}, headers=admin)).json()[
        "serverDrafts"
    ] is False
    try:
        d = (await _draft(client, h, mode="reply", conversationId=acme["conversationId"])).json()
        off = await client.post(f"/api/drafts/{d['id']}/place", json={"text": d["text"]}, headers=h)
        assert off.status_code == 403 and off.json()["error"] == "server_drafts_off"
    finally:
        await client.put("/api/admin/scoping/drafts", json={"serverDrafts": True}, headers=admin)


# --- the edit loop --------------------------------------------------------------------------------
LONG = "tell him the build is ready for UAT; hope you are having a great week"


async def _send_edited(client: httpx.AsyncClient, h: dict, edit: Any) -> dict:
    d = (await _draft(client, h, mode="new", to=[REPORT], instruction=LONG)).json()
    sent = await client.post(f"/api/drafts/{d['id']}/sent", json={"text": edit(d["text"])}, headers=h)
    assert sent.status_code == 200, sent.text
    return sent.json()


def _drop_filler(text: str) -> str:
    return text.replace(" Hope you are having a great week.", "")


async def test_edit_loop_learns_keeps_and_uses_a_rule(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState
) -> None:
    h = scanned
    await _ready(client, h)
    first = await _send_edited(client, h, _drop_filler)
    assert first["outcome"] in ("light_edit", "heavy_edit") and "avoid" in first["edits"]
    rule = next(r for r in (await client.get("/api/rules", headers=h)).json() if r["kind"] == "avoid")
    assert rule["status"] == "candidate" and rule["evidence"] == 1 and rule["scope"] == "report"
    assert (await client.put(f"/api/rules/{rule['id']}", json={"decision": "keep"}, headers=h)).status_code == 409

    await _send_edited(client, h, _drop_filler)
    await _send_edited(client, h, _drop_filler)
    rule = next(r for r in (await client.get("/api/rules", headers=h)).json() if r["kind"] == "avoid")
    # Too few emails to reports in the sample to score it against: the edits are the evidence.
    assert rule["status"] == "active" and rule["evidence"] == 3 and rule["support"] in (None, 1.0)
    assert rule["text"] == 'Don\'t write "hope you are having a great week"'
    kept = await client.put(f"/api/rules/{rule['id']}", json={"decision": "keep"}, headers=h)
    assert kept.status_code == 200 and kept.json()["status"] == "confirmed"

    # Used in the next draft: in the prompt, and the sentence is dropped in code.
    fake = await _bedrock(
        app_state, "The build is ready for UAT, ready for your testing. Hope you are having a great week."
    )
    d = (await _draft(client, h, mode="new", to=[REPORT], instruction=LONG)).json()
    assert "great week" not in d["text"].lower() and "ready for UAT" in d["text"]
    assert "Learned from the writer's own edits" in _prompt(fake)

    # A draft sent as is counts towards the send-without-edit rate.
    app_state.settings.drafter = "offline"
    await _send_edited(client, h, lambda t: t)
    s = (await client.get("/api/edits/summary", headers=h)).json()
    assert s["matched"] == 4 and s["sent_as_is"] == 1 and s["sendWithoutEditRate"] == 0.25
    assert s["byRelationship"]["report"]["matched"] == 4

    again = await client.post(f"/api/drafts/{d['id']}/sent", json={"text": "x"}, headers=h)
    assert again.status_code == 200  # the Bedrock draft was still pending
    assert (await client.post(f"/api/drafts/{d['id']}/sent", json={"text": "y"}, headers=h)).status_code == 409


async def test_purges_and_scrubs_reach_rules(client: httpx.AsyncClient, scanned: dict, app_state: AppState) -> None:
    h = scanned
    await _ready(client, h)
    for _ in range(3):
        await _send_edited(client, h, _drop_filler)
    assert any(
        r["kind"] == "avoid" and r["status"] == "active" for r in (await client.get("/api/rules", headers=h)).json()
    )

    # A never-send word inside a learned phrase: the rule is deleted.
    assert (
        await client.post("/api/controls/never-send", json={"text": "great", "kind": "word"}, headers=h)
    ).status_code == 201
    await _settle(app_state)
    assert all(r["kind"] != "avoid" for r in (await client.get("/api/rules", headers=h)).json())

    # Excluding the person the drafts went to deletes them, their evidence and the rules learned.
    rahul = _find(await _sources(client, h, "people"), "Rahul Verma")
    assert (
        await client.post("/api/controls/rules", json={"kind": "person", "id": rahul["id"]}, headers=h)
    ).status_code == 201
    await _settle(app_state)
    assert (await client.get("/api/rules", headers=h)).json() == []
    assert (await client.get("/api/edits/summary", headers=h)).json()["matched"] == 0
    receipt = next(
        r for r in (await client.get("/api/controls/receipts", headers=h)).json() if r["reason"] == "exclusion_added"
    )
    assert receipt["counts"]["drafts_deleted"] >= 3


async def test_delete_learning_removes_rules(client: httpx.AsyncClient, scanned: dict) -> None:
    h = scanned
    await _ready(client, h)
    await _send_edited(client, h, _drop_filler)
    assert (await client.get("/api/rules", headers=h)).json()
    receipt = (await client.delete("/api/learning", headers=h)).json()
    assert receipt["counts"]["style_rules_deleted"] >= 1
    assert (await client.get("/api/rules", headers=h)).json() == []


async def test_mark_as_sent_is_sample_only_and_needs_the_review(client: httpx.AsyncClient, scanned: dict) -> None:
    h = scanned
    assert (await client.post("/api/edits/sync", headers=h)).status_code == 409  # review pending
    await _ready(client, h)
    missing = await client.post("/api/drafts/00000000-0000-0000-0000-000000000000/sent", json={"text": "x"}, headers=h)
    assert missing.status_code == 404


# --- matching drafts to sent mail (Graph-style source) --------------------------------------------
async def test_sync_matches_a_sent_reply_and_respects_exclusions(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vanimo.sources.base import MessageContent, SentHeader
    from vanimo.sources.sample import MANAGER, SampleSource

    h = scanned
    await _ready(client, h)
    conv = await _thread_id(client, h, "Q4 resource plan before Thursday")
    d = (
        await _draft(
            client, h, mode="reply", conversationId=conv, instruction="tell her I'll send the plan by Wednesday"
        )
    ).json()
    reads: list[str] = []

    class SentSource(SampleSource):
        """The sample workspace plus one reply the user sent after the draft."""

        async def recent_sent(self, top: int = 5) -> list[SentHeader]:
            mine = SentHeader(
                "sent-1", conv, "Re: Q4 resource plan", datetime.now(UTC) + timedelta(minutes=5), to=(MANAGER,)
            )
            return [mine, *await super().recent_sent(top)]

        async def message(self, message_id: str) -> MessageContent | None:
            if message_id != "sent-1":
                return await super().message(message_id)
            reads.append(message_id)
            return MessageContent(
                "sent-1", conv, "Re: Q4 resource plan", datetime.now(UTC), self.me, (MANAGER,), (), "sent",
                d["text"].replace("I'll send", "I will send"),
            )  # fmt: skip

    async def source(principal: deps.CurrentPrincipal) -> SentSource:
        return SentSource(principal.email)

    client._transport.app.dependency_overrides[deps.get_source] = source  # type: ignore[attr-defined]
    try:
        synced = (await client.post("/api/edits/sync", headers=h)).json()
        assert synced["matched"] == 1 and reads == ["sent-1"]
        s = (await client.get("/api/edits/summary", headers=h)).json()
        assert s["matched"] == 1 and s["sent_as_is"] == 1  # "I'll" → "I will": under 5 % of characters
        # A second draft in the same conversation, then Meera is excluded: nothing is read.
        await _draft(client, h, mode="reply", conversationId=conv)
        meera = _find(await _sources(client, h, "people"), "Meera Iyer")
        assert (
            await client.post("/api/controls/rules", json={"kind": "person", "id": meera["id"]}, headers=h)
        ).status_code == 201
        await _settle(app_state)
        from vanimo.api import edits

        edits._last_sync.clear()
        reads.clear()
        assert (await client.post("/api/edits/sync", headers=h)).json()["matched"] == 0
        assert reads == []
    finally:
        client._transport.app.dependency_overrides.clear()  # type: ignore[attr-defined]
