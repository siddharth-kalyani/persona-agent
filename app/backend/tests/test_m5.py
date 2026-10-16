"""M5: commitments ledger, Teams chat drafting, the Teams bot, notifications."""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import jwt
import psycopg
import pytest
import respx

from tests.conftest import KID, TENANT, _b64
from tests.helpers import _find, _settle, _sources
from tests.test_drafting import FakeLlm, _draft, _ready
from vanimo.commitments.extract import find_due, looks_done, promises
from vanimo.commitments.model import BedrockExtractor, parse
from vanimo.config import Settings
from vanimo.llm.router import ModelRouter
from vanimo.state import AppState
from vanimo.teams.bot import BOT_FRAMEWORK_KEYS, BotAuth, DialogTarget, fetch_task, open_handle
from vanimo.vault import Vault

IST = ZoneInfo("Asia/Kolkata")


def _as_owner(database: dict[str, str], sql: str) -> None:
    """Test-side data changes, as the table owner (the API role sees nothing without an identity)."""
    with psycopg.connect(database["owner"].replace("postgresql+psycopg://", "postgresql://")) as conn:
        conn.execute(sql)


WED = datetime(2026, 10, 14, 6, 0, tzinfo=UTC)  # a Wednesday, 11:30 in India


# --- finding promises ------------------------------------------------------------------------------
def _whats(text: str, when: datetime = WED) -> list[str]:
    return [f.what for f in promises(text, made_at=when, tz=IST)]


def test_promises_are_the_writers_own_future_actions() -> None:
    assert _whats("Hi John,\n\nI'll revert with the final runbook tomorrow.\n\nBest regards,\n⟦ME.full⟧") == [
        "Revert with the final runbook"
    ]
    assert _whats("Yes, joining. Will share the update after.") == ["Share the update after"]
    assert _whats("sharing mine in 10 mins") == ["Sharing mine"]
    assert _whats("Noted, we will add ⟦PERSON_aaaaaaaa⟧ to the bridge.") == ["Add ⟦PERSON_aaaaaaaa⟧ to the bridge"]
    # Not promises: questions, conditions, negations, other people's actions, vague "will do".
    for text in (
        "Will you share the deck?",
        "If you need it, I'll send the deck.",
        "We will never move full card numbers.",
        "⟦PERSON_aaaaaaaa⟧ will share the deck.",
        "Will do.",
        "I shared the deck yesterday.",
        "Please send the deck by Friday.",
    ):
        assert _whats(text) == [], text


@pytest.mark.parametrize(
    ("sentence", "phrase", "local"),
    [
        ("I'll send it by Thursday EOD.", "by Thursday EOD", "2026-10-15 18:00"),
        ("I'll send it tomorrow evening.", "tomorrow evening", "2026-10-15 20:00"),
        ("We will revert this week.", "this week", "2026-10-16 18:00"),
        ("We will revert next week.", "next week", "2026-10-23 18:00"),
        ("I'll send it by Wednesday.", "by Wednesday", "2026-10-21 18:00"),  # today is Wednesday: next one
        ("I'll share it on 12 November.", "on 12 November", "2026-11-12 18:00"),
        ("I'll share it by 3 Jan.", "by 3 Jan", "2027-01-03 18:00"),  # already past this year: next year
        ("I'll send it in 10 mins.", "in 10 mins", "2026-10-14 11:40"),
        ("I'll fix it by the 31st.", "by the 31st", "2026-10-31 18:00"),
        ("I'll send it today.", "today", "2026-10-14 18:00"),
        ("I'll send it by EOD Friday.", "by EOD Friday", "2026-10-16 18:00"),  # not today's EOD
        ("I'll send it by COB Monday.", "by COB Monday", "2026-10-19 18:00"),
        ("I'll send it next Friday.", "next Friday", "2026-10-23 18:00"),  # next calendar week
        ("I'll send it next Monday.", "next Monday", "2026-10-19 18:00"),
        ("I'll send it this Friday.", "this Friday", "2026-10-16 18:00"),
        ("I'll fix it over the weekend.", "the weekend", "2026-10-17 18:00"),
    ],
)
def test_due_dates_are_resolved_in_code(sentence: str, phrase: str, local: str) -> None:
    got_phrase, due = find_due(sentence, WED, IST)
    assert got_phrase == phrase
    assert due is not None and due.astimezone(IST).strftime("%Y-%m-%d %H:%M") == local


def test_week_words_said_at_the_weekend() -> None:
    saturday = datetime(2026, 10, 17, 6, 0, tzinfo=UTC)
    _, due = find_due("We will revert this week.", saturday, IST)
    assert due is not None and due.astimezone(IST).strftime("%a %d %H:%M") == "Sun 18 18:00"
    _, due = find_due("I'll fix it this weekend.", saturday, IST)
    assert due is not None and due.astimezone(IST).strftime("%a %d") == "Sat 17"


def test_no_date_inside_a_mark_and_none_without_one() -> None:
    assert find_due("I'll send ⟦PERSON_aaaaaaaa⟧ the deck.", WED, IST) == (None, None)
    assert promises("I'll send the deck.", made_at=WED, tz=IST)[0].due_at is None


def test_looks_done_needs_delivery_and_the_same_thing() -> None:
    assert looks_done("Revert with the final runbook", "PFA the final cutover runbook (v1.3).")
    assert not looks_done("Revert with the final runbook", "Thanks for joining the call.")
    assert not looks_done("Revert with the final runbook", "The runbook review is on Friday.")


def test_model_answers_are_held_to_the_message() -> None:
    l1 = "Hi ⟦PERSON_aaaaaaaa⟧,\n\nI'll send the deck by Friday. Thanks!"
    raw = json.dumps(
        {
            "promises": [
                {"sentence": "I'll send the deck by Friday.", "what": "Send the deck", "due": "by Friday"},
                {"sentence": "I'll wire you USD 5,000.", "what": "Wire money", "due": None},  # not in the message
                {"sentence": "I'll send the deck by Friday.", "what": "Send ⟦PERSON_bbbbbbbb⟧ the deck", "due": None},
                {"sentence": "I'll send the deck by Friday.", "what": "Send it", "due": "on Monday"},  # not in it
            ]
        }
    )
    found = parse(raw, l1, made_at=WED, tz=IST)
    assert found is not None
    assert [f.what for f in found] == ["Send the deck", "Send it"]
    assert found[0].due_at is not None and found[0].due_at.astimezone(IST).day == 16
    assert found[1].due_phrase is None and found[1].due_at is None  # a date the model made up is dropped
    assert parse("not json", l1, made_at=WED, tz=IST) is None


async def test_bedrock_extractor_falls_back_to_rules(unit_settings: Settings) -> None:
    fake = FakeLlm(["sorry, I can't"])
    ex = BedrockExtractor(fake, ModelRouter(unit_settings))  # type: ignore[arg-type]
    found = await ex.find("I'll share the runbook by Thursday.", made_at=WED, tz=IST)
    assert [f.what for f in found] == ["Share the runbook"]
    # The model only ever sees the message as spotlighted data.
    assert "<message>" in fake.prompts[0][2][0]["content"]


# --- the ledger ------------------------------------------------------------------------------------
async def _ledger(client: httpx.AsyncClient, h: dict, status: str = "open") -> dict:
    resp = await client.get("/api/commitments", params={"status": status}, headers=h)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_learning_finds_promises_with_lineage(
    client: httpx.AsyncClient, scanned: dict, database: dict[str, str]
) -> None:
    h = scanned
    assert (await client.get("/api/commitments", headers=h)).json()["items"] == []
    await _ready(client, h)
    ledger = await _ledger(client, h)
    whats = {c["what"] for c in ledger["items"]}
    assert "Share the metrics" in whats  # Karan's chat: "Will share the metrics by Friday evening."
    assert ledger["label"].startswith("Offline stand-in")
    metrics = next(c for c in ledger["items"] if c["what"] == "Share the metrics")
    assert metrics["channel"] == "chat" and metrics["relationship"] == "external" and metrics["dueAt"]
    # Stored as L1 only: no name, no codename, encrypted (read as the table owner).
    url = database["owner"].replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url) as conn:
        rows = conn.execute("select text_enc, what_enc, people::text, ref_enc from vanimo.commitments").fetchall()
    dump = json.dumps([list(r) for r in rows])
    assert "Karan" not in dump and "metrics" not in dump and "smp-chat" not in dump
    # A second run finds the same promises, never duplicates them.
    before = len(ledger["items"])
    assert (await client.post("/api/learning/run", headers=h)).json()["run"]["counts"]["commitments"] == 0
    assert len((await _ledger(client, h))["items"]) == before


async def test_done_dismiss_snooze_reopen_and_precision(client: httpx.AsyncClient, scanned: dict) -> None:
    h = scanned
    await _ready(client, h)
    items = (await _ledger(client, h))["items"]
    a, b, c = items[0], items[1], items[2]
    for cid, action in ((a["id"], "done"), (b["id"], "dismiss"), (c["id"], "snooze")):
        resp = await client.put(f"/api/commitments/{cid}", json={"action": action}, headers=h)
        assert resp.status_code == 204, resp.text
    ledger = await _ledger(client, h)
    assert {i["id"] for i in ledger["items"]} >= {c["id"]} and a["id"] not in {i["id"] for i in ledger["items"]}
    snoozed = next(i for i in ledger["items"] if i["id"] == c["id"])
    assert snoozed["snoozedUntil"]
    assert ledger["precision"] == 0.5 and ledger["decided"] == 2
    assert [i["id"] for i in (await _ledger(client, h, "done"))["items"]] == [a["id"]]
    # "Not a promise" sticks: learning again doesn't reopen it.
    await client.post("/api/learning/run", headers=h)
    assert b["id"] in {i["id"] for i in (await _ledger(client, h, "dismissed"))["items"]}
    assert (await client.put(f"/api/commitments/{b['id']}", json={"action": "reopen"}, headers=h)).status_code == 204
    assert b["id"] in {i["id"] for i in (await _ledger(client, h))["items"]}
    missing = await client.put(f"/api/commitments/{uuid.uuid4()}", json={"action": "done"}, headers=h)
    assert missing.status_code == 404


async def test_exclusions_never_send_and_delete_reach_commitments(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState
) -> None:
    h = scanned
    await _ready(client, h)
    karan = [c for c in (await _ledger(client, h))["items"] if c["relationship"] == "external"]
    assert karan
    # A never-send word in a promise is re-masked where it's stored.
    assert (
        await client.post("/api/controls/never-send", json={"text": "metrics", "kind": "word"}, headers=h)
    ).status_code == 201
    await _settle(app_state)
    assert all("metrics" not in c["what"].lower() for c in (await _ledger(client, h))["items"])
    # Excluding Karan hides his promises at once and the purge deletes them.
    person = _find(await _sources(client, h, "people"), "Karan Malhotra")
    assert (
        await client.post("/api/controls/rules", json={"kind": "person", "id": person["id"]}, headers=h)
    ).status_code == 201
    await _settle(app_state)
    after = await _ledger(client, h)
    assert all(c["id"] not in {k["id"] for k in karan} for c in after["items"])
    receipt = next(
        r for r in (await client.get("/api/controls/receipts", headers=h)).json() if r["reason"] == "exclusion_added"
    )
    assert receipt["counts"]["commitments_deleted"] >= 1
    # "Delete what Vanimo learned" deletes every promise and the scan mark.
    assert (await client.delete("/api/learning", headers=h)).json()["counts"]["commitments_deleted"] >= 1
    assert (await _ledger(client, h))["items"] == []


async def test_scan_is_gated_throttled_and_reads_only_allowed_mail(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState
) -> None:
    from vanimo.commitments import scan as scanning

    h = scanned
    assert (await client.post("/api/commitments/scan", headers=h)).status_code == 409  # review pending
    await _ready(client, h)
    scanning.THROTTLE._last.clear()
    first = (await client.post("/api/commitments/scan", headers=h)).json()
    assert first["skipped"] is False and first["pending"] is False  # nothing new since the learning run
    assert (await client.post("/api/commitments/scan", headers=h)).json()["skipped"] is True  # once a minute


async def test_scan_never_reads_excluded_mail(
    scanned: dict, client: httpx.AsyncClient, app_state: AppState, database: dict[str, str]
) -> None:
    """A stub source counts what is read: an excluded sent message's text is never fetched."""
    from vanimo.api import deps
    from vanimo.commitments import scan as scanning
    from vanimo.sources.sample import SampleSource

    h = scanned
    await _ready(client, h)
    person = _find(await _sources(client, h, "people"), "Karan Malhotra")
    await client.post("/api/controls/rules", json={"kind": "person", "id": person["id"]}, headers=h)
    await _settle(app_state)
    read: list[str] = []

    class Counting(SampleSource):
        async def message(self, message_id: str):  # type: ignore[no-untyped-def]
            read.append(message_id)
            return await super().message(message_id)

        async def chat_messages(self, chat_id: str, since: datetime | None = None):  # type: ignore[no-untyped-def,override]
            read.append(chat_id)
            async for m in super().chat_messages(chat_id, since):
                yield m

    me = (await client.get("/api/me", headers=h)).json()["email"]
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[deps.get_source] = lambda: Counting(me, now=datetime.now(UTC) + timedelta(days=30))
    try:
        # Every sent message is "new" for a scan that last looked 120 days ago.
        _as_owner(database, "update vanimo.commitment_scans set scanned_until = now() - interval '59 days'")
        scanning.THROTTLE._last.clear()
        resp = await client.post("/api/commitments/scan", headers=h)
        assert resp.status_code == 200, resp.text
    finally:
        app.dependency_overrides.clear()
    sample = Counting(me, now=datetime.now(UTC) + timedelta(days=30))
    karan = "karan.malhotra@bluefinbank.example"
    with_karan = {
        m.id
        for m in await sample.all_messages()
        if m.direction == "sent" and any(a.email == karan for a in m.recipients)
    }
    assert with_karan and read  # something was read, and Karan was on some of the user's mail
    assert not with_karan & set(read)  # but none of that mail was
    assert "smp-chat-006" not in read  # the 1:1 with Karan is excluded by the roster
    assert resp.json()["excluded"] >= 1


async def test_follow_up_is_drafted_where_the_promise_was_made(client: httpx.AsyncClient, scanned: dict) -> None:
    h = scanned
    await _ready(client, h)
    items = (await _ledger(client, h))["items"]
    email = next(c for c in items if c["channel"] == "email")
    resp = await client.post(
        f"/api/commitments/{email['id']}/follow-up", json={"kind": "late", "newDate": "Monday"}, headers=h
    )
    assert resp.status_code == 200, resp.text
    d = resp.json()
    assert d["channel"] == "email" and "Monday" in d["text"] and d["id"]
    chat = next(c for c in items if c["channel"] == "chat" and c["relationship"] == "external")  # Karan, 1:1
    resp = await client.post(f"/api/commitments/{chat['id']}/follow-up", json={"kind": "done"}, headers=h)
    assert resp.status_code == 200, resp.text
    d = resp.json()
    assert d["channel"] == "chat" and d["chatUsers"] == ["karan.malhotra@bluefinbank.example"]
    # A chat message has no greeting or sign-off line added.
    assert not d["text"].rstrip().endswith(("Thanks,", "regards,")) and "Best regards" not in d["text"]
    drafts = (await client.get("/api/drafts", headers=h)).json()
    assert {x["surface"] for x in drafts} >= {"commitments"}


# --- Teams chats in the drafting service -------------------------------------------------------------
async def _chat_id(client: httpx.AsyncClient, h: dict, label: str) -> str:
    chats = (await client.get("/api/drafting/chats", headers=h)).json()
    return next(c["chatId"] for c in chats if c["label"] == label)


async def test_chat_drafts_use_the_roster_and_the_chat(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState, database: dict[str, str]
) -> None:
    h = scanned
    await _ready(client, h)
    chats = (await client.get("/api/drafting/chats", headers=h)).json()
    assert all(c["chatId"] != "smp-chat-011" for c in chats)  # hidden chats aren't offered
    rahul = next(c for c in chats if c["label"] == "Rahul Verma")
    view = (await client.get("/api/drafting/chat", params={"chatId": rahul["chatId"]}, headers=h)).json()
    assert view["messages"] and any(m["fromMe"] for m in view["messages"])
    resp = await _draft(client, h, mode="reply", channel="chat", conversationId=rahul["chatId"], surface="teams")
    assert resp.status_code == 200, resp.text
    d = resp.json()
    assert d["channel"] == "chat" and d["chatUsers"] == ["rahul.verma@kestrel.example"]
    assert d["audience"]["relationship"] == "report"
    url = database["owner"].replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url) as conn:
        row = conn.execute(
            "select channel, surface, chat_ref_enc is not null, reply_to_enc from vanimo.drafts where id = %s",
            (d["id"],),
        ).fetchone()
    assert row == ("chat", "teams", True, None)
    # The message being answered bounds the context; an unknown one is refused.
    bad = await _draft(client, h, mode="reply", channel="chat", conversationId=rahul["chatId"], messageId="nope")
    assert bad.status_code == 404 and bad.json()["error"] == "message_not_found"


async def test_excluded_and_unverifiable_chats_are_refused(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState, database: dict[str, str]
) -> None:
    h = scanned
    await _ready(client, h)
    war_room = await _chat_id(client, h, "Falcon war room")
    chat_src = _find(await _sources(client, h, "chats"), "Falcon war room")
    assert (
        await client.post("/api/controls/rules", json={"kind": "chat", "id": chat_src["id"]}, headers=h)
    ).status_code == 201
    await _settle(app_state)
    resp = await _draft(client, h, mode="reply", channel="chat", conversationId=war_room)
    assert resp.status_code == 409 and resp.json()["by"] == "you" and resp.json()["oneOffAllowed"] is True
    one_off = await _draft(client, h, mode="reply", channel="chat", conversationId=war_room, oneOff=True)
    assert one_off.status_code == 200 and one_off.json()["id"] is None
    # A meeting chat the header pass couldn't tie to its meeting can't be checked: refused.
    _as_owner(database, "update vanimo.source_chats set meeting_hash = null where chat_type = 'meeting'")
    sync = await _chat_id(client, h, "Acme weekly sync")
    resp = await _draft(client, h, mode="reply", channel="chat", conversationId=sync)
    assert resp.status_code == 403 and resp.json()["reasons"] == ["meeting_unknown"]


async def test_chat_drafts_are_purged_by_a_chat_rule_and_teach_no_email_habits(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState
) -> None:
    h = scanned
    await _ready(client, h)
    rahul = await _chat_id(client, h, "Rahul Verma")
    ids = []
    for _ in range(3):
        d = (
            await _draft(client, h, mode="reply", channel="chat", conversationId=rahul, instruction="say it's done")
        ).json()
        ids.append(d["id"])
        # Sent much shorter, without a greeting: length and greeting are email habits, never learned from chat.
        sent = await client.post(f"/api/drafts/{d['id']}/sent", json={"text": "done!"}, headers=h)
        assert sent.status_code == 200, sent.text
    learned = (await client.get("/api/rules", headers=h)).json()
    assert all(r["kind"] not in ("greeting", "sign_off", "length") for r in learned)
    chat_src = _find(await _sources(client, h, "chats"), "Rahul Verma")
    await client.post("/api/controls/rules", json={"kind": "chat", "id": chat_src["id"]}, headers=h)
    await _settle(app_state)
    receipt = next(
        r for r in (await client.get("/api/controls/receipts", headers=h)).json() if r["reason"] == "exclusion_added"
    )
    assert receipt["counts"]["drafts_deleted"] >= 3


# --- the Teams bot ----------------------------------------------------------------------------------
def _bf_token(
    rsa_key: Any, *, aud: str, service_url: str, iss: str = "https://api.botframework.com", kid: str = "bf1"
) -> str:
    now = int(time.time())
    claims = {"iss": iss, "aud": aud, "exp": now + 600, "nbf": now - 10, "serviceUrl": service_url}
    return jwt.encode(claims, rsa_key, algorithm="RS256", headers={"kid": kid})


def _activity(**extra: Any) -> dict:
    return {
        "type": "invoke",
        "name": "composeExtension/fetchTask",
        "channelId": "msteams",
        "serviceUrl": "https://smba.trafficmanager.net/in/",
        "from": {"aadObjectId": "33333333-3333-3333-3333-333333333333"},
        "channelData": {"tenant": {"id": TENANT}},
        "conversation": {"id": "19:abc@thread.v2", "conversationType": "groupChat"},
        "value": {
            "commandId": "draftReply",
            "commandContext": "message",
            "messagePayload": {"id": "1700000000000", "body": {"content": "SECRET-CONTENT the client wrote"}},
        },
        **extra,
    }


@pytest.fixture
def bf_keys(rsa_key: Any) -> dict:
    pub = rsa_key.public_key().public_numbers()
    return {"keys": [{"kty": "RSA", "kid": "bf1", "n": _b64(pub.n), "e": _b64(pub.e), "endorsements": ["msteams"]}]}


async def test_bot_requests_are_authenticated(rsa_key: Any, bf_keys: dict, unit_settings: Settings) -> None:
    unit_settings.teams_bot_id = "44444444-4444-4444-4444-444444444444"
    act = _activity()
    async with httpx.AsyncClient() as http:
        with respx.mock() as router:
            router.get(BOT_FRAMEWORK_KEYS).mock(return_value=httpx.Response(200, json=bf_keys))
            auth = BotAuth(unit_settings, http)
            good = _bf_token(rsa_key, aud=unit_settings.teams_bot_id, service_url=act["serviceUrl"])
            await auth.check(f"Bearer {good}", act)
            from vanimo.auth.entra import AuthError

            for bad, activity in (
                (_bf_token(rsa_key, aud="someone-else", service_url=act["serviceUrl"]), act),
                (_bf_token(rsa_key, aud=unit_settings.teams_bot_id, service_url="https://evil.example/"), act),
                (good, {**act, "channelId": "webchat"}),  # the key isn't endorsed for that channel
                (
                    _bf_token(rsa_key, aud=unit_settings.teams_bot_id, service_url=act["serviceUrl"], iss="https://x"),
                    act,
                ),
            ):
                with pytest.raises(AuthError):
                    await auth.check(f"Bearer {bad}", activity)
            with pytest.raises(AuthError):
                await auth.check("", act)


def test_fetch_task_hands_out_ids_only_in_an_opaque_handle(unit_settings: Settings) -> None:
    vault = Vault("x" * 40)
    unit_settings.web_url = "https://app.example"
    out = fetch_task(unit_settings, vault, _activity())
    url = out["task"]["value"]["url"]
    assert url.startswith("https://app.example/teams.html?h=") and out["task"]["type"] == "continue"
    dumped = json.dumps(out)
    assert "SECRET-CONTENT" not in dumped and "19:abc" not in dumped and "1700000000000" not in dumped
    handle = url.split("h=", 1)[1]
    oid = "33333333-3333-3333-3333-333333333333"
    target = open_handle(vault, handle, tenant=TENANT, oid=oid)
    assert target == DialogTarget("reply", "19:abc@thread.v2", "1700000000000")
    from vanimo.auth.entra import AuthError

    with pytest.raises(AuthError):
        open_handle(vault, handle, tenant=TENANT, oid=str(uuid.uuid4()))  # someone else
    with pytest.raises(AuthError):
        open_handle(vault, handle, tenant=TENANT, oid=oid, now=time.time() + 3600)  # expired
    with pytest.raises(AuthError):
        open_handle(vault, handle[:-4] + "AAAA", tenant=TENANT, oid=oid)  # tampered
    channel = fetch_task(
        unit_settings,
        vault,
        _activity(conversation={"id": "19:x@thread.tacv2;messageid=1", "conversationType": "channel"}),
    )
    h2 = channel["task"]["value"]["url"].split("h=", 1)[1]
    assert open_handle(vault, h2, tenant=TENANT, oid=oid).mode == "channel"
    with pytest.raises(AuthError):
        fetch_task(unit_settings, vault, _activity(channelData={"tenant": {"id": "other"}}))


async def test_bot_endpoint_and_dialog(
    client: httpx.AsyncClient,
    app_state: AppState,
    rsa_key: Any,
    bf_keys: dict,
    graph_mock: respx.MockRouter,
    make_token: Any,
) -> None:
    app_state.settings.teams_bot_id = "44444444-4444-4444-4444-444444444444"
    graph_mock.get(BOT_FRAMEWORK_KEYS).mock(return_value=httpx.Response(200, json=bf_keys))
    act = _activity()
    token = _bf_token(rsa_key, aud=app_state.settings.teams_bot_id, service_url=act["serviceUrl"])
    unauth = await client.post("/api/teams/messages", json=act)
    assert unauth.status_code == 401
    resp = await client.post("/api/teams/messages", json=act, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    handle = resp.json()["task"]["value"]["url"].split("h=", 1)[1]
    # The dialog, signed in as the same person, gets the chat and message back.
    me = {"Authorization": f"Bearer {make_token(oid=act['from']['aadObjectId'])}"}
    graph_mock.get("https://graph.microsoft.com/v1.0/me").mock(return_value=httpx.Response(200, json={"id": "x"}))
    out = await client.post("/api/teams/dialog", json={"handle": handle}, headers=me)
    assert out.status_code == 200, out.text
    assert out.json() == {"mode": "reply", "chatId": "19:abc@thread.v2", "messageId": "1700000000000"}
    other = {"Authorization": f"Bearer {make_token()}"}
    assert (await client.post("/api/teams/dialog", json={"handle": handle}, headers=other)).status_code == 403
    # Anything but an invoke gets an empty 200 (no chatting with the bot in the MVP).
    msg = {**act, "type": "message"}
    assert (
        await client.post("/api/teams/messages", json=msg, headers={"Authorization": f"Bearer {token}"})
    ).status_code == 200


# --- notifications ----------------------------------------------------------------------------------
async def test_notifications_are_content_free_counts(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState, database: dict[str, str]
) -> None:
    h = scanned
    await _ready(client, h)
    _as_owner(database, "update vanimo.commitments set due_at = now() - interval '1 hour' where ordinal = 0")
    out = (await client.get("/api/notifications", headers=h)).json()
    kinds = {n["kind"]: n for n in out["items"]}
    assert "commitments_due" in kinds and out["unread"] >= 1
    assert kinds["commitments_due"]["text"].endswith("due soon or overdue")
    assert kinds["commitments_due"]["teams"] == "pending"  # the sweeper delivers (or marks it off)
    again = (await client.get("/api/notifications", headers=h)).json()
    assert len(again["items"]) == len(out["items"])  # one per kind and period
    assert (await client.post("/api/notifications/read", json={}, headers=h)).status_code == 204
    assert (await client.get("/api/notifications", headers=h)).json()["unread"] == 0


async def test_sweeper_delivers_to_teams_or_marks_off(
    client: httpx.AsyncClient,
    scanned: dict,
    app_state: AppState,
    graph_mock: respx.MockRouter,
    database: dict[str, str],
) -> None:
    from vanimo import notify

    h = scanned
    await _ready(client, h)
    _as_owner(database, "update vanimo.commitments set due_at = now() - interval '1 hour'")
    made = await notify.run_once(app_state.engine, app_state.vault, zone=IST, notifier=None)
    assert made >= 1
    out = (await client.get("/api/notifications", headers=h)).json()
    assert {n["teams"] for n in out["items"] if n["kind"] == "commitments_due"} == {"off"}  # no Teams app here

    # With a Teams app, a pending one goes to the activity feed: counts only.
    sent: list[dict] = []
    oid = str(uuid.uuid4())

    def capture(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(204)

    graph_mock.post(f"https://graph.microsoft.com/v1.0/users/{oid}/teamwork/sendActivityNotification").mock(
        side_effect=capture
    )

    async def token() -> str:
        return "app-token"

    teams = notify.TeamsNotifier(
        app_state.http, app_state.settings.graph_base_url, token, "6eb7a34e-98f7-47fd-a00a-58b5f900f9be"
    )
    assert await teams.send(oid, "commitments_due", 3)
    assert sent[0]["previewText"]["content"] == "3 promises due soon or overdue"
    assert sent[0]["topic"]["webUrl"].startswith("https://teams.microsoft.com/l/entity/")
    assert not await teams.send("local:abc", "commitments_due", 1)  # never to a non-Entra account


async def test_admin_teams_switches(client: httpx.AsyncClient, database: dict[str, str], settings: Settings) -> None:
    from tests.helpers import _user

    admin = await _user(client, database, settings, role="admin")
    assert (await client.get("/api/teams/config", headers=admin)).json() == {"prefill": False, "appId": None}
    resp = await client.put(
        "/api/admin/scoping/teams", json={"teamsPrefill": True, "teamsNotifications": False}, headers=admin
    )
    assert (
        resp.status_code == 200 and resp.json()["teamsPrefill"] is True and resp.json()["teamsNotifications"] is False
    )
    assert (await client.get("/api/teams/config", headers=admin)).json()["prefill"] is True
    user = await _user(client, database, settings)
    assert (
        await client.put(
            "/api/admin/scoping/teams", json={"teamsPrefill": False, "teamsNotifications": True}, headers=user
        )
    ).status_code == 403


# --- Graph: "since" reads ---------------------------------------------------------------------------
async def test_graph_since_filters(graph_mock: respx.MockRouter) -> None:
    from vanimo.graph.client import GraphClient
    from vanimo.sources.graph import GraphSource

    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"value": []})

    graph_mock.get(url__regex=r"https://graph\.microsoft\.com/v1\.0/(me/mailFolders/sentitems/messages|chats/.+)").mock(
        side_effect=record
    )
    graph_mock.get("https://graph.microsoft.com/v1.0/me").mock(return_value=httpx.Response(200, json={"id": "me"}))
    async with httpx.AsyncClient() as http:
        src = GraphSource(GraphClient("t", http, "https://graph.microsoft.com/v1.0"))
        since = datetime(2026, 10, 1, tzinfo=UTC)
        assert [h async for h in src.sent_headers(since=since)] == []
        assert [m async for m in src.chat_messages("19:abc@thread.v2", since=since)] == []
    sent_q = seen[0].url.params
    assert sent_q["$filter"] == "sentDateTime gt 2026-10-01T00:00:00Z" and sent_q["$orderby"] == "sentDateTime asc"
    chat_q = next(r for r in seen if "/chats/" in r.url.path and r.url.path.endswith("/messages")).url.params
    assert chat_q["$filter"].startswith("lastModifiedDateTime gt") and chat_q["$orderby"] == "lastModifiedDateTime desc"


def test_kid_constant_still_imported() -> None:
    assert KID  # conftest's Entra key stays separate from the Bot Framework one
