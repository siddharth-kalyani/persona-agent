"""Fixes from the M4 review: placed drafts and the user's own replies, one draft per sent message,
content edits never becoming style, rules applied safely, Reply-To, matching budget and races,
lineage of the sent message, rejected rules, orphaned Outlook drafts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import psycopg
import pytest

from tests.helpers import _find, _settle, _sources
from tests.test_drafting import _draft, _ready, _thread_id
from tests.test_m4 import REPORT, _drop_filler, _send_edited
from vanimo.api import deps
from vanimo.controls.neversend import Matcher
from vanimo.drafting import checks as chk
from vanimo.drafting.prompt import Prompt, apply_rules
from vanimo.edits import matching
from vanimo.edits.diff import compare, style_edits
from vanimo.sources.base import Address, MessageContent, SentHeader
from vanimo.sources.sample import MANAGER, REPORTS, SampleSource
from vanimo.state import AppState

Sent = tuple[str, str, datetime, tuple[Address, ...], tuple[Address, ...], Callable[[], str]]


def _owner(database: dict[str, str], sql: str) -> list[Any]:
    with psycopg.connect(database["owner"].replace("postgresql+psycopg://", "postgresql://")) as conn:
        cur = conn.execute(sql)
        return cur.fetchall() if cur.description else []


class _Sends:
    """Install a sample source that also has the given sent messages (id, conversation, time, to,
    cc, body) — the user's real replies, as Graph's Sent Items would show them."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client
        self.sent: list[Sent] = []
        self.reads: list[str] = []
        self.on_read: Callable[[], None] | None = None
        outer = self

        class Source(SampleSource):
            async def recent_sent(self, top: int = 5) -> list[SentHeader]:
                mine = [SentHeader(i, c, "Re", at, to=to, cc=cc) for i, c, at, to, cc, _ in outer.sent]
                return [*mine, *await super().recent_sent(top)]

            async def message(self, message_id: str) -> MessageContent | None:
                hit = next((s for s in outer.sent if s[0] == message_id), None)
                if hit is None:
                    return await super().message(message_id)
                outer.reads.append(message_id)
                if outer.on_read:
                    outer.on_read()
                i, c, at, to, cc, body = hit
                return MessageContent(i, c, "Re", at, self.me, to, cc, "sent", body())

        async def source(principal: deps.CurrentPrincipal) -> Source:
            return Source(principal.email)

        client._transport.app.dependency_overrides[deps.get_source] = source  # type: ignore[attr-defined]

    def close(self) -> None:
        self.client._transport.app.dependency_overrides.clear()  # type: ignore[attr-defined]


async def _sync(client: httpx.AsyncClient, h: dict) -> dict:
    from vanimo.api import edits

    edits._last_sync.clear()
    resp = await client.post("/api/edits/sync", headers=h)
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture
def sends(client: httpx.AsyncClient):  # type: ignore[no-untyped-def]
    s = _Sends(client)
    yield s
    s.close()


# --- units ---------------------------------------------------------------------------------------
def test_content_swaps_are_never_style() -> None:
    for a, b in [
        ("accept", "decline"),
        ("approved", "rejected"),
        ("last", "next"),
        ("office", "warehouse"),
        ("a", "the"),
    ]:
        assert [e.kind for e in style_edits(f"We {a} it now.", f"We {b} it now.")] == ["content"], (a, b)
    assert [e.value for e in style_edits("Could you please share it?", "Could you pls share it?")] == ["please -> pls"]
    base = (
        "Thanks for the update on the migration plan and the cutover schedule for the weekend. I'll confirm the "
        "vendor slots by tomorrow and we approve the budget of 5000 for testing before the steering committee meets."
    )
    assert compare(base, base.replace("approve", "reject")).outcome == "light_edit"
    assert compare(base, base.replace("5000", "50000")).outcome == "light_edit"
    assert compare(base, base.replace("I'll", "I will")).outcome == "sent_as_is"


def test_apply_rules_keeps_tokens_numbers_links_and_contractions() -> None:
    p = Prompt(system=[], user="", target_words=20, bounds=(5, 40), greeting="", sign_off="")
    p.prefer, p.no_exclamations, p.drop = [("please", "pls"), ("can", "could")], True, ["do not hesitate"]
    out = apply_rules("Talk to ⟦PERSON_aaaaaaaa.full⟧ today. Do not hesitate to ask. The 2.5 release is out!", p)
    assert out == "Talk to ⟦PERSON_aaaaaaaa.full⟧ today. The 2.5 release is out."
    assert (
        apply_rules("We can't wait! See https://x.example/#!/page", p) == "We can't wait. See https://x.example/#!/page"
    )
    # The user's own "never use" phrases only ask the model to revise; they never delete text in code.
    mine = Prompt(system=[], user="", target_words=20, bounds=(5, 40), greeting="", sign_off="", dont=["hi", "ASAP"])
    text = "I think this is the last step. Can you send the signed contract ASAP?"
    assert apply_rules(text, mine) == text


def test_reply_to_redirects() -> None:
    known, org = {"acmeretail.example"}, {"kestrel.example"}
    john = Address("john@acmeretail.example", "John")
    fake = chk.reply_to_redirect([(john, Address("billing@acmeretai1.example"))], known_domains=known, org_domains=org)
    assert [c.code for c in fake] == ["lookalike_reply_to"] and chk.blocked(fake)
    other = chk.reply_to_redirect([(john, Address("ap@finance.example"))], known_domains=known, org_domains=org)
    assert [(c.code, c.severity) for c in other] == [("reply_to_differs", "warn")]


async def test_graph_thread_headers_read_reply_to() -> None:
    import respx

    from vanimo.graph.client import GraphClient
    from vanimo.sources.graph import GraphSource

    with respx.mock(assert_all_called=False) as r:
        r.get("https://graph.microsoft.com/v1.0/me").mock(
            return_value=httpx.Response(200, json={"id": "u", "mail": "me@contoso.example"})
        )
        listing = r.get("https://graph.microsoft.com/v1.0/me/messages").mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "m1",
                            "conversationId": "c",
                            "sentDateTime": "2026-10-13T10:00:00Z",
                            "from": {"emailAddress": {"address": "john@acme.example"}},
                            "replyTo": [{"emailAddress": {"address": "billing@acme-pay.example"}}],
                        }
                    ]
                },
            )
        )
        headers = await GraphSource(GraphClient("t", httpx.AsyncClient())).thread_headers("c")
    assert headers[0].reply_to[0].email == "billing@acme-pay.example"
    assert "billing@acme-pay.example" in {a.email for a in headers[0].participants}  # exclusions see it too
    assert "replyTo" in str(listing.calls[0].request.url.params)


# --- placed drafts and the user's own reply ---------------------------------------------------------
async def test_placed_draft_then_own_reply_is_tidied(
    client: httpx.AsyncClient,
    scanned: dict,
    sends: _Sends,
    database: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    h = scanned
    await _ready(client, h)
    await client.put("/api/drafting/settings", json={"outlookDrafts": True, "staleDays": 3}, headers=h)
    conv = await _thread_id(client, h, "Q4 resource plan before Thursday")
    recipients: list[Any] = []

    async def capture(self: Any, item_id: str, to: list[Address], cc: list[Address]) -> None:
        recipients.append(([a.email for a in to], [a.email for a in cc]))

    monkeypatch.setattr(SampleSource, "set_draft_recipients", capture)
    first = (await client.post("/api/queue/prepare", json={"conversationId": conv}, headers=h)).json()
    second = (await client.post("/api/queue/prepare", json={"conversationId": conv}, headers=h)).json()
    assert first["placed"] and second["placed"]
    # Addressed to exactly whom Vanimo checked; the earlier unused draft was replaced.
    assert recipients[-1] == (["meera.iyer@kestrel.example"], [])
    states = dict(_owner(database, "select id::text, placed_state from vanimo.drafts where placed_state is not null"))
    assert states[first["draft"]["id"]] == "replaced" and states[second["draft"]["id"]] == "placed"

    # The user writes their own reply instead; matching doesn't pretend they sent Vanimo's draft.
    sends.sent.append(("own-1", conv, datetime.now(UTC) + timedelta(minutes=5), (MANAGER,), (), lambda: "Done, sent."))
    await _sync(client, h)
    assert dict(_owner(database, "select id::text, placed_state from vanimo.drafts"))[second["draft"]["id"]] == "placed"
    tidied = (await client.post("/api/queue/tidy", headers=h)).json()
    assert tidied == {"replaced": 1}


async def test_placing_needs_the_opt_in_and_one_claim(client: httpx.AsyncClient, scanned: dict) -> None:
    h = scanned
    await _ready(client, h)
    conv = await _thread_id(client, h, "Acme go-live date?")
    d = (await _draft(client, h, mode="reply", conversationId=conv)).json()
    off = await client.post(f"/api/drafts/{d['id']}/place", json={"text": d["text"]}, headers=h)
    assert off.status_code == 409 and off.json()["error"] == "outlook_drafts_off"
    await client.put("/api/drafting/settings", json={"outlookDrafts": True, "staleDays": 3}, headers=h)
    import asyncio

    a, b = await asyncio.gather(
        client.post(f"/api/drafts/{d['id']}/place", json={"text": d["text"]}, headers=h),
        client.post(f"/api/drafts/{d['id']}/place", json={"text": d["text"]}, headers=h),
    )
    assert sorted([a.status_code, b.status_code]) == [200, 409]


# --- matching ---------------------------------------------------------------------------------------
async def test_one_sent_reply_counts_once(client: httpx.AsyncClient, scanned: dict, sends: _Sends) -> None:
    h = scanned
    await _ready(client, h)
    conv = await _thread_id(client, h, "Q4 resource plan before Thursday")
    drafts = [(await _draft(client, h, mode="reply", conversationId=conv)).json() for _ in range(3)]
    sends.sent.append(
        ("own-1", conv, datetime.now(UTC) + timedelta(minutes=5), (MANAGER,), (), lambda: drafts[-1]["text"])
    )
    synced = await _sync(client, h)
    assert synced["matched"] == 1 and sends.reads == ["own-1"]
    s = (await client.get("/api/edits/summary", headers=h)).json()
    assert s["matched"] == 1 and s["drafts"].get("superseded") == 2


async def test_controls_changed_during_matching_wins(
    client: httpx.AsyncClient, scanned: dict, sends: _Sends, database: dict[str, str]
) -> None:
    h = scanned
    await _ready(client, h)
    conv = await _thread_id(client, h, "Q4 resource plan before Thursday")
    d = (await _draft(client, h, mode="reply", conversationId=conv)).json()
    sends.sent.append(("own-1", conv, datetime.now(UTC) + timedelta(minutes=5), (MANAGER,), (), lambda: d["text"]))
    sends.on_read = lambda: _owner(
        database,
        "insert into vanimo.controls_state (owner_user_id, tenant_id, version) select id, tenant_id, 1 "
        "from vanimo.users on conflict (owner_user_id) do update set version = vanimo.controls_state.version + 1",
    )
    assert (await _sync(client, h))["matched"] == 0  # not recorded; tried again next time
    sends.on_read = None
    assert (await _sync(client, h))["matched"] == 1


async def test_read_budget_never_marks_drafts_unmatched(
    client: httpx.AsyncClient, scanned: dict, sends: _Sends, database: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    h = scanned
    await _ready(client, h)
    convs = [await _thread_id(client, h, s) for s in ("Q4 resource plan before Thursday", "Acme go-live date?")]
    for c in convs:
        await _draft(client, h, mode="reply", conversationId=c)
    _owner(database, "update vanimo.drafts set created_at = now() - interval '4 days'")
    when = datetime.now(UTC) - timedelta(days=4) + timedelta(hours=1)
    sends.sent += [
        ("s-a", convs[0], when, (MANAGER,), (), lambda: "Done."),
        ("s-b", convs[1], when, (MANAGER,), (), lambda: "Done."),
    ]
    monkeypatch.setattr(matching, "MAX_FETCHES", 1)
    first = await _sync(client, h)
    assert first["matched"] == 1 and first["unmatched"] == 0 and first["pending"] == 1
    assert (await _sync(client, h))["matched"] == 1  # the other one, on the next sync


async def test_sent_message_people_join_the_lineage(
    client: httpx.AsyncClient, scanned: dict, sends: _Sends, app_state: AppState
) -> None:
    h = scanned
    await _ready(client, h)
    conv = await _thread_id(client, h, "Q4 resource plan before Thursday")
    d = (await _draft(client, h, mode="reply", conversationId=conv)).json()
    # The real reply also cc'd Rahul.
    sends.sent.append(
        ("own-1", conv, datetime.now(UTC) + timedelta(minutes=5), (MANAGER,), (REPORTS[0],), lambda: d["text"])
    )
    assert (await _sync(client, h))["matched"] == 1
    rahul = _find(await _sources(client, h, "people"), "Rahul Verma")
    assert (
        await client.post("/api/controls/rules", json={"kind": "person", "id": rahul["id"]}, headers=h)
    ).status_code == 201
    await _settle(app_state)
    assert (await client.get("/api/edits/summary", headers=h)).json()["matched"] == 0


# --- rules ----------------------------------------------------------------------------------------
async def test_rejection_survives_a_purge(client: httpx.AsyncClient, scanned: dict, app_state: AppState) -> None:
    h = scanned
    await _ready(client, h)
    for _ in range(3):
        await _send_edited(client, h, _drop_filler)
    rule = next(r for r in (await client.get("/api/rules", headers=h)).json() if r["kind"] == "avoid")
    assert (await client.put(f"/api/rules/{rule['id']}", json={"decision": "reject"}, headers=h)).status_code == 200
    rahul = _find(await _sources(client, h, "people"), "Rahul Verma")
    await client.post("/api/controls/rules", json={"kind": "person", "id": rahul["id"]}, headers=h)
    await _settle(app_state)
    kept = [r for r in (await client.get("/api/rules", headers=h)).json() if r["id"] == rule["id"]]
    assert kept and kept[0]["status"] == "rejected" and kept[0]["value"] == ""  # the decision stays, not the text
    _ = REPORT


async def test_purged_placed_drafts_are_tidied_later(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState, database: dict[str, str]
) -> None:
    h = scanned
    await _ready(client, h)
    await client.put("/api/drafting/settings", json={"outlookDrafts": True, "staleDays": 3}, headers=h)
    conv = await _thread_id(client, h, "Q4 resource plan before Thursday")
    assert (await client.post("/api/queue/prepare", json={"conversationId": conv}, headers=h)).json()["placed"]
    receipt = (await client.delete("/api/learning", headers=h)).json()
    assert receipt["counts"]["drafts_deleted"] >= 1
    assert _owner(database, "select count(*) from vanimo.orphan_placements")[0][0] >= 1
    assert (await client.post("/api/queue/tidy", headers=h)).json() == {"orphan_removed_stale": 1}
    assert _owner(database, "select count(*) from vanimo.orphan_placements")[0][0] == 0
    _ = Matcher
