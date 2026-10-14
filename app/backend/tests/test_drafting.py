"""M3 drafting: unit tests for the checks, the output gate, routing and the offline stand-in, then
end to end on the sample workspace (review → learn → draft → checks → feedback → purges)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import psycopg
import pytest

from tests.helpers import _find, _settle, _sources, _user
from tests.test_learning import _learn, _review
from vanimo.config import Settings
from vanimo.controls.neversend import Matcher, Term
from vanimo.drafting import checks as chk
from vanimo.drafting.gate import clean, gate, render
from vanimo.drafting.generate import instruction_to_body
from vanimo.drafting.prompt import greeting, sign_off, style_problems, target
from vanimo.llm.router import Generated, ModelRouter
from vanimo.sources.base import Address
from vanimo.state import AppState

ME = "me@kestrel.example"


# --- checks ---------------------------------------------------------------------------------------
def test_lookalike_domains() -> None:
    assert chk.lookalike("c1oudnest.example", "cloudnest.example")
    assert chk.lookalike("acmeretai.example", "acmeretail.example")
    assert chk.lookalike("cloudnest-billing.example", "cloudnest.example")
    assert chk.lookalike("rnicrosoft.example", "microsoft.example")
    assert not chk.lookalike("cards.bluefinbank.example", "bluefinbank.example")  # a subdomain is the same org
    assert not chk.lookalike("orionhealth.example", "acmeretail.example")


def test_recipient_checks() -> None:
    known = {"acmeretail.example", "cloudnest.example"}
    org = {"kestrel.example"}
    found = chk.recipient_checks(
        [Address("tom@c1oudnest.example"), Address("x@newco.example"), Address("y@gmail.com")],
        thread_people=[Address("meera@kestrel.example")],
        known_domains=known,
        org_domains=org,
        me=ME,
    )
    codes = {c.code: c.severity for c in found}
    assert codes == {
        "lookalike_domain": "block",
        "new_domain": "warn",
        "personal_address": "warn",
        "external_added": "warn",
    }
    # A look-alike in the thread itself doesn't vouch for itself.
    again = chk.recipient_checks(
        [Address("tom@c1oudnest.example")],
        thread_people=[Address("tom@c1oudnest.example")],
        known_domains=known,
        org_domains=org,
        me=ME,
    )
    assert [c.code for c in again] == ["lookalike_domain"]
    assert chk.sender_lookalike([Address("tom@c1oudnest.example")], known_domains=known, org_domains=org)


def test_invented_facts() -> None:
    grounding = "Can you confirm the go-live date? The sandbox is ready Tuesday. Budget USD 18,400."
    draft = (
        "Go-live is on 28 Oct. We will deliver the runbook by Friday. The sandbox is ready Tuesday. "
        "The budget stays at $18,400. I'll also send a revised staffing plan."
    )
    found = {c.code: c.message for c in chk.invented_facts(draft, grounding)}
    assert "28 Oct" in found["invented_fact"]
    assert "Friday" in found["invented_commitment"]
    assert "unrequested_promise" in found
    assert "Tuesday" not in json.dumps(found) and "18,400" not in json.dumps(found)
    assert chk.invented_facts("Thanks, the sandbox is ready Tuesday.", grounding) == []


def test_payment_change_and_regulated_ids() -> None:
    bec = "Please note our bank details have changed. Kindly process the payment to the new account by today EOD."
    found = chk.payment_change([bec], "Sure, will do.")
    assert [c.code for c in found] == ["payment_change"] and chk.blocked(found)
    assert chk.payment_change(["Thanks for the update on the sprint."], "ok") == []
    assert [c.code for c in chk.payment_change(["Can you wire the payment today please"], "ok")] == ["urgent_payment"]
    assert {c.code for c in chk.regulated_ids("My PAN is ABCPE1234F and password: Kestrel@2026")} == {
        "regulated_id",
        "secret",
    }


def test_greeting_and_other_client() -> None:
    to = [Address("lisa.chen@acmeretail.example", "Lisa Chen")]
    assert chk.greeting_mismatch("Hi John,\n\nPlease see below.", to)[0].code == "greeting_mismatch"
    assert chk.greeting_mismatch("Hi Lisa,\n\nThanks.", to) == []
    assert chk.greeting_mismatch("Hi all,\n\nThanks.", to) == []
    accounts = [chk.ClientAccount("Bluefin", frozenset({"h-bluefin"}))]
    hashes = {"acmeretail.example": ["h-acme"], "bluefinbank.example": ["h-bluefin"]}
    found = chk.cross_client("The Bluefin migration plan is attached.", to, accounts, lambda d: hashes.get(d, []))
    assert [c.code for c in found] == ["other_client_named"]
    to_bluefin = [Address("karan@bluefinbank.example")]
    assert chk.cross_client("Bluefin plan", to_bluefin, accounts, lambda d: hashes.get(d, [])) == []


# --- output gate ---------------------------------------------------------------------------------
def test_gate_cleans_and_never_reveals_unknown_tokens() -> None:
    body = (
        "Hi ⟦PERSON_aaaaaaaa⟧,\n\n**Sure.** Please see https://evil.example/x and https://ok.example/doc. "
        "Ask ⟦PERSON_deadbeef⟧ to call 98765 43210 or mail x@evil.example.\n\nBest regards,\n⟦ME.full⟧"
    )
    g = gate(
        body,
        prompt_marks={"⟦PERSON_aaaaaaaa⟧", "⟦ME.full⟧"},
        grounding="the doc is at https://ok.example/doc",
        matcher=Matcher([]),
    )
    assert g.blocked is None
    assert g.body.startswith("Sure.") and "Best regards" not in g.body and "⟦ME" not in g.body
    assert "[link removed]" in g.body and "https://ok.example/doc" in g.body and "evil" not in g.body
    assert "[name]" in g.body and "deadbeef" not in g.body
    assert "[phone number]" in g.body and "[email address]" in g.body
    assert {n.code for n in g.notes} == {"unknown_marker", "link_removed", "contact_removed"}


def test_gate_blocks_regulated_ids_and_masks_never_send() -> None:
    blocked = gate("Your PAN is ABCPE1234F.", prompt_marks=set(), grounding="", matcher=Matcher([]))
    assert blocked.blocked == "regulated_id_in_output"
    m = Matcher([Term("abcd1234", "Falcon", "codename")])
    g = gate("The Falcon plan is ready.", prompt_marks=set(), grounding="", matcher=m)
    assert "⟦NS_abcd1234⟧" in g.body
    shown, removed = render(g.body, values={}, allowed_marks=set(), allowed_terms={}, blocked_matcher=m)
    assert shown == "The [removed] plan is ready." and removed == 1
    allowed, removed = render(
        g.body, values={}, allowed_marks=set(), allowed_terms={"abcd1234": "Falcon"}, blocked_matcher=Matcher([])
    )
    assert allowed == "The Falcon plan is ready." and removed == 0


def test_clean_keeps_a_closing_sentence() -> None:
    assert clean("We're on track.\nThanks for your help.") == "We're on track.\nThanks for your help."
    assert clean("We're on track.\n\nThanks,\n⟦ME⟧") == "We're on track."


# --- persona controls, routing, offline -----------------------------------------------------------
def _r(name: str, email: str) -> Any:
    from vanimo.drafting.context import Recipient

    first = name.split()[0]
    return Recipient(
        Address(email, name),
        {
            "full": (f"⟦PERSON_{first[:4].lower():0<8}.full⟧", name),
            "first": (f"⟦PERSON_{first[:4].lower():0<8}⟧", first),
        },
        f"⟦PERSON_{first[:4].lower():0<8}.full⟧",
    )


def test_greeting_and_sign_off_from_the_card() -> None:
    card = {
        "greetings": [["Dear {first},", 0.6], ["Hi {first},", 0.4]],
        "sign_offs": [["Best regards,\n{me_full}", 1.0]],
    }
    one = greeting(card, [_r("John Miller", "john@acme.example")])
    assert one.startswith("Dear ⟦PERSON_") and one.endswith("⟧,")
    two = greeting(card, [_r("John Miller", "j@a.example"), _r("Lisa Chen", "l@a.example")])
    assert " and ⟦PERSON_" in two
    many = greeting(card, [_r(n, f"{n[0]}@a.example") for n in ("Ann B", "Bob C", "Cat D")])
    assert many == "Dear all,"
    assert sign_off(card) == "Best regards,\n⟦ME.full⟧"
    assert greeting({"greetings": [["(none)", 0.7], ["Hi {first},", 0.3]]}, []) == ""
    unnamed = greeting({"greetings": [["Hi {first},", 1.0]]}, [])
    assert unnamed == "Hi,"
    words, (low, high) = target({"length": {"median": 40, "p25": 20, "p75": 60}}, 0)
    assert words == 40 and low < 40 < high


def test_style_problems() -> None:
    from vanimo.drafting.prompt import Prompt

    p = Prompt(system=[], user="", target_words=20, bounds=(5, 40), greeting="", sign_off="", dont=["circle back"])
    assert style_problems("I hope this email finds you well. Let's circle back on this.", p)
    assert style_problems("Sounds good, the plan works for us and we can start Monday.", p) == []


def test_router(unit_settings: Settings) -> None:
    router = ModelRouter(unit_settings)
    haiku, sonnet = unit_settings.model_default, unit_settings.model_premium
    r = router.route_draft(mode="reply", relationship="peer", target_words=60, quality="auto", premium_used_today=0)
    assert (r.tier, r.model_id) == ("default", haiku)
    r = router.route_draft(mode="new", relationship="external", target_words=60, quality="auto", premium_used_today=0)
    assert (r.tier, r.model_id, r.reason) == ("premium", sonnet, "new_to_external")
    r = router.route_draft(mode="reply", relationship="peer", target_words=60, quality="premium", premium_used_today=99)
    assert (r.tier, r.reason) == ("default", "premium_quota_used")
    r = router.route_draft(mode="reply", relationship="peer", target_words=300, quality="auto", premium_used_today=0)
    assert r.reason == "long_draft"


def test_offline_instruction_rules() -> None:
    assert instruction_to_body("tell him we'll share the runbook by Thursday", formal=False, kindly=False) == (
        "We'll share the runbook by Thursday."
    )
    assert instruction_to_body("ask her to review the UAT checklist", formal=False, kindly=False) == (
        "Could you please review the UAT checklist?"
    )
    assert instruction_to_body("ask them to review the plan", formal=True, kindly=True) == "Kindly review the plan."
    assert instruction_to_body(
        "thank him for the quick turnaround; confirm the cutover is on Saturday", formal=True, kindly=False
    ) == ("Thank you for the quick turnaround. Confirming that the cutover is on Saturday.")


# --- end to end on the sample workspace ------------------------------------------------------------
async def _ready(client: httpx.AsyncClient, h: dict) -> None:
    await _review(client, h)
    await _learn(client, h)


async def _thread_id(client: httpx.AsyncClient, h: dict, subject: str) -> str:
    threads = (await client.get("/api/drafting/threads", headers=h)).json()
    return next(t["conversationId"] for t in threads if t["subject"] == subject)


async def _draft(client: httpx.AsyncClient, h: dict, **body: Any) -> httpx.Response:
    return await client.post("/api/drafts", json=body, headers=h)


async def test_drafting_needs_the_review(client: httpx.AsyncClient, scanned: dict) -> None:
    resp = await _draft(client, scanned, mode="new", instruction="hello", to=[{"email": "a@kestrel.example"}])
    assert resp.status_code == 409 and resp.json() == {"error": "review_pending"}


async def test_offline_reply_in_your_voice(
    client: httpx.AsyncClient,
    scanned: dict,
    app_state: AppState,
    database: dict[str, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    h = scanned
    await _ready(client, h)
    status = (await client.get("/api/drafting/status", headers=h)).json()
    assert status["generator"] == "offline" and status["reviewDone"] and status["learnedItems"] > 0

    threads = (await client.get("/api/drafting/threads", headers=h)).json()
    assert threads[0]["subject"] == "Updated bank details for CloudNest invoice"
    conv = await _thread_id(client, h, "Q4 resource plan before Thursday")
    shown = (await client.get("/api/drafting/thread", params={"conversationId": conv}, headers=h)).json()
    assert "Q4 resource plan" in shown["messages"][-1]["text"]

    canary = "VNMCANARY-instr-0123456789ab"
    resp = await _draft(
        client, h, mode="reply", conversationId=conv, instruction=f"tell her I'll share the plan by Wednesday {canary}"
    )
    assert resp.status_code == 200, resp.text
    d = resp.json()
    assert d["generator"] == "offline" and "Offline stand-in" in d["label"]
    assert d["audience"]["relationship"] == "manager" and d["audience"]["label"] == "your manager"
    assert d["audience"]["to"][0]["email"].startswith("meera.iyer@")
    assert d["text"].startswith("Hi Meera,") and "⟦" not in d["text"]
    assert "I'll share the plan by Wednesday" in d["text"]
    assert d["insertAllowed"] and d["id"] and d["learned"] and d["basedOn"] >= 3
    # "by Wednesday" came from the instruction: not an invented commitment.
    assert not any(c["code"].startswith("invented") for c in d["checks"])

    # Stored as L1 only: no names or the canary readable even by the table owner.
    url = database["owner"].replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url) as conn:
        rows = conn.execute("select tenant_id, owner_user_id, text_enc from vanimo.drafts").fetchall()
        dump = "\n".join(str(r) for r in conn.execute("select * from vanimo.drafts").fetchall())
    assert "Meera" not in dump and canary not in dump and "Wednesday" not in dump  # encrypted at rest
    l1 = app_state.vault.decrypt_user(rows[0][0], rows[0][1], rows[0][2], "draft_text") or ""
    assert "⟦PERSON_" in l1 and "⟦ME⟧" in l1 and "Meera" not in l1 and "kestrel.example" not in l1  # and L1 inside
    # Logs: codes and timings only.
    out = capsys.readouterr().out
    assert canary not in out and "Wednesday" not in out and "Meera" not in out

    # Feedback and the list (metadata only).
    assert (
        await client.post(f"/api/drafts/{d['id']}/feedback", json={"outcome": "inserted", "rating": "good"}, headers=h)
    ).status_code == 204
    listed = (await client.get("/api/drafts", headers=h)).json()
    assert listed[0]["id"] == d["id"] and listed[0]["outcome"] == "inserted" and "text" not in listed[0]


async def test_bec_thread_blocks_insert(client: httpx.AsyncClient, scanned: dict) -> None:
    h = scanned
    await _ready(client, h)
    conv = await _thread_id(client, h, "Updated bank details for CloudNest invoice")
    d = (await _draft(client, h, mode="reply", conversationId=conv)).json()
    codes = {c["code"]: c["severity"] for c in d["checks"]}
    assert codes["payment_change"] == "block" and codes["lookalike_sender"] == "block"
    assert codes["lookalike_domain"] == "block"  # replying goes to the look-alike address
    assert d["insertAllowed"] is False
    assert "50100234567891" not in d["text"] and "HDFC0001234" not in d["text"]


async def test_new_email_checks_and_never_send(client: httpx.AsyncClient, scanned: dict, app_state: AppState) -> None:
    h = scanned
    assert (
        await client.post("/api/controls/never-send", json={"text": "Falcon", "kind": "codename"}, headers=h)
    ).status_code == 201
    await _settle(app_state)
    await _ready(client, h)
    d = (
        await _draft(
            client,
            h,
            mode="new",
            surface="outlook",
            to=[{"email": "john.miller@acmeretail.example", "name": "John Miller"}],
            subject="Plan",
            instruction="tell him the Project Falcon plan is ready; ask him to share the UAT feedback",
        )
    ).json()
    assert d["audience"]["relationship"] == "external"
    assert "[removed]" in d["text"] and "Falcon" not in d["text"]
    assert any(c["code"] == "never_send_removed" for c in d["checks"])
    assert d["text"].startswith(("Dear John,", "Hi John,"))

    # Pre-send checks on the user's own text.
    chk_resp = await client.post(
        "/api/drafts/check",
        json={
            "body": "Hi Rahul,\n\nMy PAN is ABCPE1234F. The Falcon plan is attached.",
            "to": [{"email": "john.miller@acmeretail.example", "name": "John Miller"}],
        },
        headers=h,
    )
    codes = {c["code"] for c in chk_resp.json()["checks"]}
    assert {"greeting_mismatch", "regulated_id", "never_send_word"} <= codes
    look = await client.post(
        "/api/drafts/check", json={"body": "Hello", "to": [{"email": "john@acmeretai1.example"}]}, headers=h
    )
    assert look.json()["insertAllowed"] is False


async def test_excluded_conversations(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState, database: dict[str, str], settings: Settings
) -> None:
    h = scanned
    await _ready(client, h)
    conv = await _thread_id(client, h, "Acme go-live date?")
    first = (await _draft(client, h, mode="reply", conversationId=conv)).json()
    assert first["id"]

    john = _find(await _sources(client, h, "people"), "John Miller")
    assert (
        await client.post("/api/controls/rules", json={"kind": "person", "id": john["id"]}, headers=h)
    ).status_code == 201
    await _settle(app_state)
    # The purge reached the earlier draft to him.
    assert all(x["id"] != first["id"] for x in (await client.get("/api/drafts", headers=h)).json())
    threads = (await client.get("/api/drafting/threads", headers=h)).json()
    assert next(t for t in threads if t["conversationId"] == conv)["excludedBy"] == "you"

    refused = await _draft(client, h, mode="reply", conversationId=conv)
    assert refused.status_code == 409
    assert refused.json()["error"] == "conversation_excluded" and refused.json()["oneOffAllowed"] is True
    assert (await client.get("/api/drafting/thread", params={"conversationId": conv}, headers=h)).status_code == 409
    one_off = (await _draft(client, h, mode="reply", conversationId=conv, oneOff=True)).json()
    assert one_off["id"] is None and one_off["oneOff"] is True
    assert all(x["relationship"] != "external" for x in (await client.get("/api/drafts", headers=h)).json())

    # An organisation rule can't be overridden, not even one-off.
    admin = await _user(client, database, settings, role="admin")
    acc = await client.post(
        "/api/admin/scoping/accounts",
        headers=admin,
        json={"name": "Orion Health", "mode": "excluded", "domains": ["orionhealth.example"], "sensitiveWords": []},
    )
    assert acc.status_code in (200, 201), acc.text
    try:
        orion = await _draft(
            client,
            h,
            mode="new",
            oneOff=True,
            to=[{"email": "emily.park@orionhealth.example"}],
            instruction="ask her for the workshop notes",
        )
        assert orion.status_code == 403 and orion.json()["by"] == "organisation"
    finally:
        account = next(a for a in acc.json()["accounts"] if a["name"] == "Orion Health")
        await client.delete(f"/api/admin/scoping/accounts/{account['id']}", headers=admin)
        await _settle(app_state)

    # "Delete what Vanimo learned" deletes drafts too.
    await _draft(
        client, h, mode="new", to=[{"email": "rahul.verma@kestrel.example"}], instruction="ask him for the checklist"
    )
    receipt = (await client.delete("/api/learning", headers=h)).json()
    assert receipt["counts"]["drafts_deleted"] >= 1
    assert (await client.get("/api/drafts", headers=h)).json() == []


async def test_rate_limit(client: httpx.AsyncClient, scanned: dict, app_state: AppState) -> None:
    h = scanned
    await _ready(client, h)
    app_state.settings.drafts_per_minute = 2
    body = {"mode": "new", "to": [{"email": "rahul.verma@kestrel.example"}], "instruction": "ask him for the checklist"}
    assert (await _draft(client, h, **body)).status_code == 200
    assert (await _draft(client, h, **body)).status_code == 200
    third = await _draft(client, h, **body)
    assert third.status_code == 429 and third.json()["error"] == "too_many_drafts"


class FakeLlm:
    """Stands in for Claude on Bedrock: returns what a misbehaving model might write."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.prompts: list[Any] = []

    async def generate(self, *, model: str, system: Any, messages: list[dict[str, Any]], max_tokens: int) -> Generated:
        self.prompts.append((model, system, messages))
        return Generated(self.replies[min(len(self.prompts) - 1, len(self.replies) - 1)], model, 12.0, 34.0)


async def test_bedrock_path_through_the_gate(client: httpx.AsyncClient, scanned: dict, app_state: AppState) -> None:
    h = scanned
    await _ready(client, h)
    fake = FakeLlm(
        [
            "Hi Meera,\n\n**Sure** — I'll send the Q4 plan by Friday 31 Oct. Details: https://evil.example/q4. "
            "Ping ⟦PERSON_deadbeef⟧ if needed.\n\nThanks,\n⟦ME⟧"
        ]
    )
    app_state._llm = fake  # type: ignore[assignment]
    app_state.settings.drafter = "bedrock"
    conv = await _thread_id(client, h, "Q4 resource plan before Thursday")
    d = (await _draft(client, h, mode="reply", conversationId=conv, quality="premium")).json()
    assert d["generator"] == "bedrock" and d["tier"] == "premium" and d["modelId"] == app_state.settings.model_premium
    assert d["text"].startswith("Hi Meera,") and d["text"].count("Hi Meera") == 1
    assert "evil.example" not in d["text"] and "[link removed]" in d["text"] and "[name]" in d["text"]
    codes = {c["code"] for c in d["checks"]}
    assert {"invented_commitment", "link_removed", "unknown_marker"} <= codes

    # The prompt the model saw: L1 only, the thread spotlighted as data.
    _, system, messages = fake.prompts[0]
    prompt = json.dumps(system, ensure_ascii=False) + json.dumps(messages, ensure_ascii=False)
    assert "Meera" not in prompt and "kestrel.example" not in prompt
    assert "<thread>" in prompt and "⟦PERSON_" in prompt and "cache_control" in prompt

    fake.replies = ["Sure. My PAN is ABCPE1234F."]
    fake.prompts.clear()
    blocked = await _draft(client, h, mode="reply", conversationId=conv)
    assert blocked.status_code == 422 and blocked.json() == {
        "error": "draft_blocked",
        "reason": "regulated_id_in_output",
    }


# --- Microsoft Graph (mocked) ----------------------------------------------------------------------
GRAPH = "https://graph.microsoft.com/v1.0"


async def test_graph_inbox_headers_drafts_and_manager() -> None:
    import respx

    from vanimo.graph.client import GraphClient
    from vanimo.sources.graph import GraphSource

    def msg(i: str, conv: str, when: str, sender: str, draft: bool = False) -> dict[str, Any]:
        return {
            "id": i,
            "conversationId": conv,
            "subject": "S",
            "receivedDateTime": when,
            "sentDateTime": when,
            "from": {"emailAddress": {"address": sender, "name": sender.split("@")[0]}},
            "toRecipients": [{"emailAddress": {"address": "me@contoso.example"}}],
            "isDraft": draft,
        }

    with respx.mock(assert_all_called=False) as r:
        r.get(f"{GRAPH}/me").mock(
            return_value=httpx.Response(200, json={"id": "u-me", "displayName": "Me", "mail": "me@contoso.example"})
        )
        r.get(f"{GRAPH}/me/manager").mock(
            return_value=httpx.Response(200, json={"displayName": "Boss", "mail": "Boss@Contoso.example"})
        )
        inbox = r.get(f"{GRAPH}/me/mailFolders/inbox/messages").mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": [
                        msg("a2", "c-a", "2026-10-13T10:00:00Z", "ann@fabrikam.example"),
                        msg("a1", "c-a", "2026-10-12T10:00:00Z", "ann@fabrikam.example"),
                        msg("b1", "c-b", "2026-10-11T10:00:00Z", "bob@fabrikam.example"),
                    ]
                },
            )
        )
        thread = r.get(f"{GRAPH}/me/messages").mock(
            side_effect=lambda req: httpx.Response(
                200,
                json={
                    "value": [
                        msg("x1", "c+a/b", "2026-10-12T10:00:00Z", "ann@fabrikam.example"),
                        msg("x2", "c+a/b", "2026-10-13T10:00:00Z", "me@contoso.example", draft=True),
                    ]
                    if "c-a_b" in str(req.url)
                    else []
                },
            )
        )
        source = GraphSource(GraphClient("tok", httpx.AsyncClient()))
        received = await source.recent_received(10)
        assert [h.id for h in received] == ["a2", "b1"]  # one per conversation, the latest
        assert "body" not in str(inbox.calls[0].request.url.params).lower()
        manager = await source.manager()
        assert manager is not None and manager.email == "boss@contoso.example"

        from vanimo.drafting.context import _thread_headers

        headers = await _thread_headers(source, "c+a/b")  # the add-in's form → Graph's URL-safe form
        assert [h.id for h in headers] == ["x1"]  # the unsent draft is not part of the thread
        assert thread.call_count == 2


# --- review fixes (M3 review) ----------------------------------------------------------------------
def test_eval_baseline_matches_two_line_sign_offs() -> None:
    from vanimo.learning import style
    from vanimo.learning.evaluate import score
    from vanimo.llm.offline import Exemplar, OfflineDrafter

    actual = "Hi ⟦PERSON_aaaaaaaa⟧,\n\nThe build is ready for UAT.\n\nThanks,\n⟦ME⟧"
    ex = [style.Example(actual, "peer", "email", "english", "update", f"t{i}") for i in range(4)]
    cards = {k: c for k, (_, c) in style.build_cards(ex).items()}
    assert cards[style.slice_key()]["sign_offs"][0][0] == "Thanks,\n{me}"
    pool = [Exemplar("x", actual, "is it ready?", "peer", "email", None)]
    d = OfflineDrafter().draft("is it ready?", relationship="peer", channel="email", cards=cards, pool=pool)
    assert score(d.text, actual)["sign_off_match"] == 1.0


def test_directory_name_forms() -> None:
    from vanimo.redaction.pipeline import _name_parts

    assert _name_parts("Iyer, Meera") == ["Meera", "Iyer"]
    assert _name_parts("Dr. R. Anil Kumar (Contractor)") == ["Anil", "Kumar"]


def _no_purge(monkeypatch: pytest.MonkeyPatch) -> None:
    """Purge and scrub jobs don't run: what's stored still holds the excluded or never-send data,
    as in the minutes before the job finishes. The live checks must cover it."""

    async def later(*_: Any, **__: Any) -> None:
        return None

    monkeypatch.setattr("vanimo.api.controls.run_job", later)


async def _bedrock(app_state: AppState, reply: str = "Will do.") -> FakeLlm:
    fake = FakeLlm([reply])
    app_state._llm = fake  # type: ignore[assignment]
    app_state.settings.drafter = "bedrock"
    return fake


def _prompt(fake: FakeLlm) -> str:
    """Everything the model was given on the last call, as plain text."""
    _, system, messages = fake.prompts[-1]
    return "\n".join([*(b["text"] for b in system), *(m["content"] for m in messages)])


async def test_other_audiences_messages_are_only_shapes(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState
) -> None:
    h = scanned
    await _ready(client, h)
    fake = await _bedrock(app_state)
    to = [{"email": "emily.park@orionhealth.example", "name": "Emily Park"}]
    cc = [{"email": "meera.iyer@kestrel.example", "name": "Meera Iyer"}]
    d = await _draft(client, h, mode="new", to=to, cc=cc, instruction="ask her for the workshop notes")
    assert d.status_code == 200, d.text
    # Nothing Emily and Meera didn't both receive is shown word for word (Acme mail cc'd Meera is not).
    assert 'kind="message"' not in _prompt(fake)
    # To John alone, his own threads may be given verbatim.
    await _draft(client, h, mode="new", to=[{"email": "john.miller@acmeretail.example"}], instruction="ask for UAT")
    assert 'kind="message"' in _prompt(fake)


async def test_live_rules_win_before_the_purge_runs(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = scanned
    await _ready(client, h)
    _no_purge(monkeypatch)
    fake = await _bedrock(app_state)
    john = [{"email": "john.miller@acmeretail.example", "name": "John Miller"}]
    await _draft(client, h, mode="new", to=john, instruction="ask him for the UAT feedback")
    assert "coupon" in _prompt(fake).lower()  # the UAT thread he was on is an example

    # A never-send word, before the scrub job has re-masked the stored examples.
    assert (
        await client.post("/api/controls/never-send", json={"text": "coupon", "kind": "word"}, headers=h)
    ).status_code == 201
    await _draft(client, h, mode="new", to=john, instruction="ask him for the UAT feedback")
    assert "coupon" not in _prompt(fake).lower() and "⟦NS_" in _prompt(fake)

    # A person rule, before the purge job has deleted what was learned with her.
    lisa = _find(await _sources(client, h, "people"), "Lisa Chen")
    assert (
        await client.post("/api/controls/rules", json={"kind": "person", "id": lisa["id"]}, headers=h)
    ).status_code == 201
    await _draft(client, h, mode="new", to=john, instruction="ask him for the UAT feedback")
    assert "re-test" not in _prompt(fake).lower()  # the UAT thread with Lisa is no longer an example


async def test_thread_rule_refuses_drafting(client: httpx.AsyncClient, scanned: dict, app_state: AppState) -> None:
    h = scanned
    await _ready(client, h)
    thread = _find(await _sources(client, h, "threads"), "Re: Acme UAT sign-off")
    assert (
        await client.post("/api/controls/rules", json={"kind": "thread", "id": thread["id"]}, headers=h)
    ).status_code == 201
    await _settle(app_state)
    conv = next(
        t["conversationId"]
        for t in (await client.get("/api/drafting/threads", headers=h)).json()
        if t["subject"] and "Acme UAT sign-off" in t["subject"]
    )
    refused = await _draft(client, h, mode="reply", conversationId=conv)
    assert refused.status_code == 409 and refused.json()["reasons"] == ["thread"]


async def test_add_in_conversation_id_form_is_matched_to_the_rule() -> None:
    """Office.js may give the ID in standard base64 where Graph uses the URL-safe form: the rule
    (keyed on Graph's form) must still apply."""
    from datetime import UTC, datetime

    from vanimo.controls.engine import ExclusionEngine, UserRule
    from vanimo.drafting.context import Directory, DraftError, gather
    from vanimo.redaction.pipeline import Person
    from vanimo.sources.base import MessageHeader

    def hasher(kind: str, value: str) -> str:
        import hashlib

        return hashlib.sha256(f"{kind}:{value}".encode()).hexdigest()

    graph_id = "AAQkADk-abc_def="
    fetched: list[str] = []

    class Source:
        kind = "graph"

        async def thread_headers(self, conversation_id: str) -> list[MessageHeader]:
            if conversation_id != graph_id:
                return []
            ann = Address("ann@fabrikam.example", "Ann")
            return [MessageHeader("m1", graph_id, datetime.now(UTC), ann, (Address(ME),), (), "received")]

        async def message(self, message_id: str) -> None:
            fetched.append(message_id)

    engine = ExclusionEngine(
        hasher=hasher, user_rules=[UserRule("r1", "thread", hasher("thread", graph_id))], self_email=ME
    )
    directory = Directory(Person("Me", ME), None, frozenset(), frozenset({"kestrel.example"}), ())
    with pytest.raises(DraftError) as err:
        await gather(
            Source(),  # type: ignore[arg-type]
            ex_engine=engine,
            matcher=Matcher([]),
            hasher=hasher,
            directory=directory,
            self_email=ME,
            mode="reply",
            conversation_id="AAQkADk+abc/def=",
            to=None,
            cc=None,
            subject=None,
            instruction=None,
        )
    assert err.value.code == "conversation_excluded" and fetched == []


async def test_a_rule_added_while_drafting_wins(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState, database: dict[str, str]
) -> None:
    h = scanned
    await _ready(client, h)

    class Racing(FakeLlm):
        async def generate(self, **kw: Any) -> Generated:  # type: ignore[override]
            # The user changes their controls while the model is writing.
            url = database["owner"].replace("postgresql+psycopg://", "postgresql://")
            with psycopg.connect(url) as conn:
                conn.execute(
                    "insert into vanimo.controls_state (owner_user_id, tenant_id, version) "
                    "select id, tenant_id, 1 from vanimo.users on conflict (owner_user_id) "
                    "do update set version = vanimo.controls_state.version + 1"
                )
            return await super().generate(**kw)

    app_state._llm = Racing(["Will do."])  # type: ignore[assignment]
    app_state.settings.drafter = "bedrock"
    before = len((await client.get("/api/drafts", headers=h)).json())
    d = (
        await _draft(client, h, mode="new", to=[{"email": "rahul.verma@kestrel.example"}], instruction="ask for it")
    ).json()
    assert d["id"] is None and any(c["code"] == "controls_changed" for c in d["checks"])
    assert len((await client.get("/api/drafts", headers=h)).json()) == before
