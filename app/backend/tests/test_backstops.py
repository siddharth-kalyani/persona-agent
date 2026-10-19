"""F11 redaction backstops: Comprehend at S5, Bedrock Guardrails around every model call, Macie over L1
snapshots (with their offline stand-ins), the tenant pause and the admin view. AWS clients are fakes."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import httpx
import psycopg
import pytest
from pydantic import ValidationError

from tests.helpers import _settle, _user
from vanimo.backstops import Backstops, current, install
from vanimo.backstops import events as backstop_events
from vanimo.backstops.guardrail import (
    BedrockGuardrail,
    GuardrailBlocked,
    GuardrailUnavailable,
    OfflineGuardrail,
    kinds_of,
)
from vanimo.backstops.macie import MacieFinding, parse, poll_round
from vanimo.backstops.pii import (
    MAX_CHUNK_BYTES,
    ComprehendDetector,
    Finding,
    OfflinePiiDetector,
    PiiUnavailable,
    chunks,
)
from vanimo.backstops.snapshots import export_user, key_for
from vanimo.config import Settings
from vanimo.controls.neversend import Matcher
from vanimo.db.session import UserRef
from vanimo.llm.router import LlmClient, ModelRouter
from vanimo.redaction.pipeline import BackstopUnavailable, Gazetteer, Person, RedactionBlocked, Redactor
from vanimo.state import AppState

TENANT = "11111111-1111-1111-1111-111111111111"
CLIENT_ID = "22222222-2222-2222-2222-222222222222"


def _hasher(kind: str, value: str) -> str:
    return hashlib.sha256(f"{kind}:{value}".encode()).hexdigest()


def at(text: str, sub: str, kind: str, score: float = 0.99) -> Finding:
    i = text.index(sub)
    return Finding(i, i + len(sub), kind, score)


class Fixed:
    """A PiiDetector returning what `fn` finds in the text it is sent (and remembering that text)."""

    name = "offline"
    label = "test detector"

    def __init__(self, fn: Callable[[str], list[Finding]] = lambda t: []) -> None:
        self.fn = fn
        self.sent: list[str] = []

    async def detect(self, text: str) -> list[Finding]:
        self.sent.append(text)
        return self.fn(text)


class Down:
    name = "comprehend"
    label = "down"

    async def detect(self, text: str) -> list[Finding]:
        raise PiiUnavailable("comprehend_unavailable")


def _redactor(pii: Any, scope: str = "all", people: list[tuple[str, str]] | None = None) -> Redactor:
    g = Gazetteer(me=Person("Siddharth Kalyani", "siddharth.kalyani@intuitive.ai"))
    for name, email in people or []:
        g.add(name, email)
    return Redactor(Matcher([]), g, _hasher, pii=pii, pii_scope=scope)


# --- S5: the redactor and its backstop ----------------------------------------------------------
async def test_backstop_sees_only_text_our_stages_already_masked() -> None:
    det = Fixed()
    r = _redactor(det, people=[("Meera Iyer", "meera.iyer@kestrel.example")])
    await r.redact("Meera's PAN is ABCPE1234F, mail meera.iyer@kestrel.example or call 98765 43210")
    sent = det.sent[0]
    for raw in ("Meera", "ABCPE1234F", "meera.iyer@kestrel.example", "98765 43210"):
        assert raw not in sent
    assert "[PAN]" in sent and "⟦PERSON_" in sent


async def test_backstop_findings_become_tokens_and_slots() -> None:
    text = "Ask Arjun Mehta to post it to 22 Residency Road; his Aadhaar 2341 2341 2346 is on file. Due 5 May."

    def find(t: str) -> list[Finding]:
        return [
            at(t, "Arjun Mehta", "NAME"),
            at(t, "22 Residency Road", "ADDRESS"),
            at(t, "5 May", "DATE_TIME"),  # not identifying: left alone
        ]

    out = await _redactor(Fixed(find)).redact(text)
    assert "Arjun" not in out.text and "Residency" not in out.text
    assert "[address]" in out.text and "[Aadhaar number]" in out.text  # ours caught the Aadhaar first
    assert "5 May" in out.text
    tok = next(t for t in out.tokens if t.startswith("⟦PERSON_"))
    assert tok.endswith(".full⟧") and out.tokens[tok] == ("person", "Arjun Mehta")
    assert out.counts["s5_backstop"] == 2 and out.counts["name"] == 1 and out.counts["address"] == 1


async def test_low_scores_and_findings_inside_marks_are_ignored() -> None:
    def find(t: str) -> list[Finding]:
        tok_end = t.index("⟧") + 1
        return [
            Finding(0, tok_end, "NAME", 0.99),  # the whole ⟦PERSON_…⟧ token: nothing outside it
            at(t, "Priya", "NAME", 0.4),  # below the NAME threshold
            Finding(t.index("⟦"), t.index("Kumar") + len("Kumar"), "NAME", 0.95),  # token + one more word
        ]

    r = _redactor(Fixed(find), people=[("Anil Rao", "anil.rao@kestrel.example")])
    out = await r.redact("Anil Rao Kumar met Priya")
    assert "Kumar" not in out.text and "Priya" in out.text
    assert out.text.count("⟦PERSON_") == 2


async def test_unknown_name_keeps_honorific_outside_and_same_token_twice() -> None:
    r = _redactor(Fixed(lambda t: [at(t, "Kavya-ji", "NAME")] if "Kavya-ji" in t else [at(t, "Kavya", "NAME")]))
    a = await r.redact("Thanks Kavya-ji!")
    b = await r.redact("Kavya will join.")
    assert "-ji!" in a.text and "Kavya" not in a.text
    assert a.text.split("-ji")[0].removeprefix("Thanks ") == b.text.split(" will")[0]


async def test_unreachable_backstop_blocks_the_item() -> None:
    with pytest.raises(BackstopUnavailable) as caught:
        await _redactor(Down()).redact("Hello there")
    assert isinstance(caught.value, RedactionBlocked) and caught.value.reason == "pii_backstop_unavailable"


async def test_flagged_scope_sends_only_items_with_identifiers() -> None:
    det = Fixed()
    r = _redactor(det, scope="flagged")
    await r.redact("Lunch at one?")
    assert det.sent == []
    await r.redact("PAN ABCPE1234F attached")
    assert len(det.sent) == 1


async def test_redactor_uses_the_installed_backstop_by_default() -> None:
    det = Fixed()
    previous = install(Backstops(pii=det, guardrail=OfflineGuardrail()))
    try:
        r = Redactor(Matcher([]), Gazetteer(), _hasher)
        await r.redact("hello")
        assert det.sent == ["hello"] and current().pii is det
    finally:
        install(previous)


async def test_offline_stand_in_finds_titled_names_and_addresses() -> None:
    text = "Mr. Vikram Sethi lives at 14 Hill View Road, Pune 411001. Flat 7B too. My name is Neha Rao."
    found = {text[f.start : f.end]: f.type for f in await OfflinePiiDetector().detect(text)}
    assert found["Vikram Sethi"] == "NAME" and found["Neha Rao"] == "NAME"
    assert any("Hill View Road" in k for k, t in found.items() if t == "ADDRESS")
    assert "Flat 7B" in found
    assert await OfflinePiiDetector().detect("The Q4 plan is due on Friday, thanks all.") == []


# --- Comprehend client ----------------------------------------------------------------------------
class FakeComprehend:
    def __init__(self, entities: Callable[[str], list[dict]] | None = None, fail: bool = False) -> None:
        self.entities = entities or (lambda t: [])
        self.fail = fail
        self.calls: list[str] = []

    def detect_pii_entities(self, Text: str, LanguageCode: str) -> dict:
        assert LanguageCode == "en"
        self.calls.append(Text)
        if self.fail:
            raise RuntimeError("AccessDenied for text 'Rahul'")
        return {"Entities": self.entities(Text)}


async def test_comprehend_offsets_cache_and_chunks() -> None:
    def ents(t: str) -> list[dict]:
        i = t.find("Ramesh")
        return [{"Type": "NAME", "Score": 0.98, "BeginOffset": i, "EndOffset": i + 6}] if i >= 0 else []

    fake = FakeComprehend(ents)
    det = ComprehendDetector("ap-south-1", client=fake)
    text = "नमस्ते 🙂 Ramesh"  # multi-byte text before the name: offsets are characters
    found = await det.detect(text)
    assert [(text[f.start : f.end], f.type) for f in found] == [("Ramesh", "NAME")]
    await det.detect(text)
    assert len(fake.calls) == 1  # cached
    assert await det.detect("  ... ") == [] and len(fake.calls) == 1  # nothing to look at

    big = ("x" * 1000 + "\n") * 200 + "Ramesh"
    found = await det.detect(big)
    assert len(fake.calls) > 2 and all(len(c.encode()) <= MAX_CHUNK_BYTES for c in fake.calls[1:])
    assert [big[f.start : f.end] for f in found] == ["Ramesh"]


def test_chunks_cover_the_text_exactly_under_the_byte_limit() -> None:
    text = "é" * 30 + " " + "word " * 50 + "ü" * 70
    parts = chunks(text, limit=64)
    assert "".join(p for _, p in parts) == text
    assert all(len(p.encode()) <= 64 for _, p in parts)
    assert all(text[o : o + len(p)] == p for o, p in parts)


async def test_comprehend_failure_and_bad_offsets_fail_closed(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(PiiUnavailable):
        await ComprehendDetector("ap-south-1", client=FakeComprehend(fail=True)).detect("Rahul says hi")
    bad = FakeComprehend(lambda t: [{"Type": "NAME", "Score": 1, "BeginOffset": 0, "EndOffset": 999}])
    with pytest.raises(PiiUnavailable):
        await ComprehendDetector("ap-south-1", client=bad).detect("Rahul says hi")
    assert "Rahul" not in capsys.readouterr().out  # only the error type is logged


# --- Guardrails ----------------------------------------------------------------------------------
class FakeBedrock:
    def __init__(self, response: dict | None = None, fail: bool = False) -> None:
        self.response = response or {"action": "NONE"}
        self.fail = fail
        self.calls: list[dict] = []

    def apply_guardrail(self, **kw: Any) -> dict:
        self.calls.append(kw)
        if self.fail:
            raise RuntimeError("ThrottlingException")
        return self.response


INTERVENED = {
    "action": "GUARDRAIL_INTERVENED",
    "assessments": [
        {
            "sensitiveInformationPolicy": {
                "piiEntities": [
                    {"type": "NAME", "match": "Rahul Verma", "action": "BLOCKED"},
                    {"type": "EMAIL", "match": "r@x.example", "action": "NONE"},
                ],
                "regexes": [{"name": "india_pan", "match": "ABCPE1234F", "action": "BLOCKED"}],
            }
        }
    ],
}


async def test_guardrail_blocks_with_types_only_and_neutralises_marks() -> None:
    fake = FakeBedrock(INTERVENED)
    g = BedrockGuardrail("gr-1", "3", "ap-south-1", client=fake)
    with pytest.raises(GuardrailBlocked) as caught:
        await g.check("OUTPUT", ["Hi ⟦PERSON_3fa2c1d0⟧, your [PAN] is ready"])
    assert caught.value.kinds == {"NAME": 1, "india_pan": 1}
    assert "Rahul" not in repr(caught.value.kinds) and "ABCPE" not in repr(caught.value.kinds)
    sent = fake.calls[0]
    assert sent["guardrailIdentifier"] == "gr-1" and sent["guardrailVersion"] == "3" and sent["source"] == "OUTPUT"
    assert "⟦" not in sent["content"][0]["text"]["text"] and "[PAN]" not in sent["content"][0]["text"]["text"]


async def test_guardrail_outage_fails_closed_and_clean_text_passes() -> None:
    with pytest.raises(GuardrailUnavailable):
        await BedrockGuardrail("g", "1", "ap-south-1", client=FakeBedrock(fail=True)).check("INPUT", ["hello"])
    await BedrockGuardrail("g", "1", "ap-south-1", client=FakeBedrock()).check("INPUT", ["hello"])
    # Other policies count by name; metrics riding along in an assessment don't.
    other = {"assessments": [{"topicPolicy": {"topics": [{"name": "x"}]}, "invocationMetrics": {"latency": 1}}]}
    assert kinds_of(other) == {"policy:topicPolicy": 1}
    assert kinds_of({"assessments": [{"invocationMetrics": {"latency": 1}}]}) == {}


async def test_offline_guardrail_blocks_raw_identifiers_not_marks() -> None:
    g = OfflineGuardrail()
    await g.check("INPUT", ["Hi ⟦PERSON_3fa2c1d0⟧, call ⟦PHONE_1a2b3c4d⟧ about [PAN]"])
    with pytest.raises(GuardrailBlocked) as caught:
        await g.check("OUTPUT", ["Send it to rahul@kestrel.example, PAN ABCPE1234F"])
    assert caught.value.kinds == {"email": 1, "PAN": 1}


class FakeAnthropic:
    """The Bedrock Messages client: messages.stream(...) as an async context manager."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls = 0
        self.messages = self

    @asynccontextmanager
    async def stream(self, **kw: Any) -> AsyncIterator[Any]:
        self.calls += 1
        reply = self.reply

        async def chunks() -> AsyncIterator[str]:
            for part in (reply[: len(reply) // 2], reply[len(reply) // 2 :]):
                yield part

        yield SimpleNamespace(text_stream=chunks())


@pytest.fixture
def model_settings() -> Settings:
    return Settings(env="test", entra_tenant_id=TENANT, entra_client_id=CLIENT_ID, cors_origins=[])


async def test_model_input_is_checked_before_the_call(model_settings: Settings) -> None:
    fake = FakeAnthropic("fine")
    blocked: list[GuardrailBlocked] = []

    async def on_block(b: GuardrailBlocked) -> None:
        blocked.append(b)

    llm = LlmClient(model_settings, ModelRouter(model_settings), OfflineGuardrail(), on_block=on_block, client=fake)
    with pytest.raises(GuardrailBlocked):
        await llm.generate(
            model=model_settings.model_default,
            system="Write as ⟦ME⟧.",
            messages=[{"role": "user", "content": [{"type": "text", "text": "PAN ABCPE1234F"}]}],
        )
    assert fake.calls == 0 and blocked[0].source == "INPUT"


async def test_model_output_is_checked_before_anyone_sees_it(model_settings: Settings) -> None:
    fake = FakeAnthropic("Sure, mail rahul@kestrel.example")
    llm = LlmClient(model_settings, ModelRouter(model_settings), OfflineGuardrail(), client=fake)
    with pytest.raises(GuardrailBlocked) as caught:
        await llm.generate(model=model_settings.model_default, system="s", messages=[{"role": "user", "content": "hi"}])
    assert caught.value.source == "OUTPUT"
    # Content the guardrail can't read (an image) is never sent unchecked.
    with pytest.raises(GuardrailUnavailable):
        await llm.generate(
            model=model_settings.model_default,
            system="s",
            messages=[{"role": "user", "content": [{"type": "image", "source": {"data": "..."}}]}],
        )
    seen: list[str] = []
    with pytest.raises(GuardrailBlocked):
        async for chunk in llm.stream_text(model=model_settings.model_default, system="s", user_text="hi"):
            seen.append(chunk)
    assert seen == []  # no part of a blocked answer is ever released
    ok = LlmClient(model_settings, ModelRouter(model_settings), OfflineGuardrail(), client=FakeAnthropic("All good."))
    out = await ok.generate(model=model_settings.model_default, system="s", messages=[{"role": "user", "content": "x"}])
    assert out.text == "All good."


# --- Macie findings -------------------------------------------------------------------------------
def _finding(bucket: str, key: str, fid: str = "f-1") -> dict:
    return {
        "id": fid,
        "category": "CLASSIFICATION",
        "severity": {"description": "High"},
        "resourcesAffected": {"s3Bucket": {"name": bucket}, "s3Object": {"key": key, "eTag": '"abc123"'}},
        "classificationDetails": {
            "result": {
                "sensitiveData": [
                    {
                        "category": "PERSONAL_INFORMATION",
                        "detections": [
                            {
                                "type": "NAME",
                                "count": 2,
                                "occurrences": {"records": [{"recordIndex": 4}, {"recordIndex": 9}]},
                            }
                        ],
                    }
                ],
                "customDataIdentifiers": {
                    "detections": [
                        {"name": "vanimo-in-dev-aadhaar", "count": 1, "occurrences": {"records": [{"recordIndex": 4}]}}
                    ]
                },
            }
        },
    }


def test_macie_findings_name_the_user_and_types_only() -> None:
    t, u = uuid.uuid4(), uuid.uuid4()
    f = parse(_finding("snap", f"l1/{t}/{u}.jsonl"), "snap")
    assert f == MacieFinding("f-1", UserRef(t, u), {"NAME": 2, "vanimo-in-dev-aadhaar": 1}, "high", "abc123", (4, 9))
    assert parse(_finding("other", f"l1/{t}/{u}.jsonl"), "snap") is None
    assert parse(_finding("snap", "l1/not-a-user.jsonl"), "snap") is None
    assert parse({**_finding("snap", f"l1/{t}/{u}.jsonl"), "category": "POLICY"}, "snap") is None
    assert parse({**_finding("snap", f"l1/{t}/{u}.jsonl"), "id": None}, "snap") is None  # malformed: skipped


def test_deployed_settings_require_the_real_backstops() -> None:
    base = {
        "env": "dev",
        "enable_password_auth": True,
        "ref_hmac_key": "k" * 40,
        "vault_master_key": "v" * 40,
    }
    with pytest.raises(ValidationError) as caught:
        Settings(**base)
    msg = str(caught.value)
    assert "VANIMO_PII_DETECTOR=comprehend" in msg and "VANIMO_GUARDRAIL=bedrock" in msg and "VANIMO_MACIE=aws" in msg
    ok = Settings(
        **base,
        pii_detector="comprehend",
        guardrail="bedrock",
        guardrail_id="gr-1",
        guardrail_version="1",
        macie="aws",
        l1_snapshot_bucket="vanimo-snapshots",
    )
    assert ok.macie == "aws"
    with pytest.raises(ValidationError):
        Settings(env="local", guardrail="bedrock")  # no guardrail ID


# --- end to end: snapshots, findings, the pause ---------------------------------------------------
async def _learned_user(client: httpx.AsyncClient, database: dict[str, str], settings: Settings) -> tuple[dict, str]:
    h = await _user(client, database, settings)
    assert (await client.post("/api/controls/scan", headers=h)).status_code == 202
    assert (await client.post("/api/controls/review", json={"outcome": "finished"}, headers=h)).status_code == 200
    run = await client.post("/api/learning/run", headers=h)
    assert run.status_code == 202 and run.json()["run"]["status"] == "done", run.text
    items = (await client.get("/api/learning/items", params={"limit": 5}, headers=h)).json()["items"]
    return h, items[0]["id"]


def _owner(database: dict[str, str]) -> psycopg.Connection:
    return psycopg.connect(database["owner"].replace("postgresql+psycopg://", "postgresql://"), autocommit=True)


def _plant(database: dict[str, str], app_state: AppState, item_id: str, raw: str) -> UserRef:
    """Puts raw text into one stored L1 item, as a redaction bug would."""
    with _owner(database) as conn:
        t, u = conn.execute("select tenant_id, owner_user_id from vanimo.l1_items where id = %s", (item_id,)).fetchone()
        conn.execute(
            "update vanimo.l1_items set text_enc = %s where id = %s",
            (app_state.vault.encrypt_user(t, u, raw, "l1_text"), item_id),
        )
    return UserRef(t, u)


async def test_offline_macie_finding_pauses_the_tenant_until_an_admin_resumes(
    client: httpx.AsyncClient, database: dict[str, str], settings: Settings, app_state: AppState
) -> None:
    h, item = await _learned_user(client, database, settings)
    admin = await _user(client, database, settings, role="admin")
    _plant(database, app_state, item, "Sure, my PAN is ABCPE1234F")
    try:
        out = await client.post("/api/admin/backstops/snapshots", headers=admin)
        assert out.status_code == 200 and out.json()["findings"] >= 1, out.text
        assert (await client.get("/api/me", headers=h)).json()["pipelinePaused"] is True
        # No content is read, redacted or drafted for anyone in the organisation meanwhile.
        refused = await client.post("/api/learning/run", headers=h)
        assert refused.status_code == 423 and refused.json() == {"error": "pipeline_paused"}
        draft = await client.post(
            "/api/drafts", json={"mode": "new", "to": [{"email": "a@b.example"}], "instruction": "hi"}, headers=h
        )
        assert draft.status_code == 423 and draft.json() == {"error": "pipeline_paused"}, draft.text
        status = (await client.get("/api/admin/backstops", headers=admin)).json()
        assert status["paused"]["reason"] == "macie_finding"
        ev = next(e for e in status["events"] if e["source"] == "macie")
        assert ev["kinds"] == {"PAN": 1} and ev["outcome"] == "finding" and "ABCPE" not in json.dumps(status)
        assert {b["key"]: b["mode"] for b in status["backstops"]} == {
            "comprehend": "offline",
            "guardrail": "offline",
            "macie": "offline",
        }
        assert ev["flaggedItems"] == 1 and ev["purgedAt"] is None  # the finding names the row
        assert (await client.get("/api/admin/backstops", headers=h)).status_code == 403
        assert (await client.post("/api/admin/backstops/resume", headers=h)).status_code == 403
        assert (await client.post(f"/api/admin/backstops/events/{ev['id']}/purge", headers=h)).status_code == 403
        # The admin removes exactly the flagged item, without seeing it.
        purged = await client.post(f"/api/admin/backstops/events/{ev['id']}/purge", headers=admin)
        assert purged.json() == {"removed": 1}
        assert (await client.post("/api/admin/backstops/events/999999999/purge", headers=admin)).status_code == 404
    finally:
        resumed = await client.post("/api/admin/backstops/resume", headers=admin)
    assert resumed.json() == {"resumed": True}
    assert (await client.get("/api/me", headers=h)).json()["pipelinePaused"] is False
    ids = [i["id"] for i in (await client.get("/api/learning/items", params={"limit": 200}, headers=h)).json()["items"]]
    assert item not in ids
    # The snapshot without it is clean: resuming sticks.
    await client.post("/api/admin/backstops/snapshots", headers=admin)
    assert (await client.get("/api/me", headers=h)).json()["pipelinePaused"] is False


class FakeStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.fail_delete = False
        self.puts = 0

    async def put(self, key: str, body: bytes) -> str:
        self.puts += 1
        self.objects[key] = body
        return hashlib.md5(body).hexdigest()  # noqa: S324 - S3's ETag for a single-part upload

    async def delete(self, key: str) -> None:
        if self.fail_delete:
            raise RuntimeError("s3 down")
        self.objects.pop(key, None)


async def test_aws_snapshot_holds_l1_only_and_purges_delete_it(
    client: httpx.AsyncClient, database: dict[str, str], settings: Settings, app_state: AppState
) -> None:
    h, _ = await _learned_user(client, database, settings)
    with _owner(database) as conn:
        t, u = conn.execute(
            "select tenant_id, owner_user_id from vanimo.l1_items order by created_at desc limit 1"
        ).fetchone()
        token_values = [
            app_state.vault.decrypt_user(t, u, r[0], "l1_token")
            for r in conn.execute("select value_enc from vanimo.l1_tokens where owner_user_id = %s", (u,))
        ]
    ref = UserRef(t, u)
    store = FakeStore()
    b = app_state.backstops
    b.macie_mode, b.snapshot_store = "aws", store
    try:
        done = await export_user(app_state.engine, app_state.vault, b, ref)
        body = store.objects[key_for(ref)].decode()
        lines = [json.loads(x) for x in body.splitlines()]
        assert done.stored and done.items == len(lines) > 0
        assert {x["t"] for x in lines} >= {"l1_items", "style_cards"}
        # No row ID or other number of ours in the object: nothing Vanimo writes can look like an Aadhaar
        # number. The manifest (in the database) names each line's row.
        assert all(set(x) == {"t", "f", "text"} for x in lines)
        names = [v for v in token_values if v and len(v) > 3 and "@" not in v]
        assert names and not any(n in body for n in names)  # token values never leave the vault
        # Unchanged: not uploaded again (Macie re-reads only new or changed objects).
        again = await export_user(app_state.engine, app_state.vault, b, ref)
        assert again.stored and not again.uploaded and store.puts == 1
        # Any deletion of L1, by any path, makes the snapshot due at once.
        with _owner(database) as conn:
            conn.execute(
                "delete from vanimo.l1_items where id = "
                "(select id from vanimo.l1_items where owner_user_id = %s limit 1)",
                (u,),
            )
            stale = conn.execute(
                "select changes > exported_changes from vanimo.l1_snapshots where owner_user_id = %s", (u,)
            ).fetchone()[0]
            due = conn.execute("select user_id from vanimo_private.snapshot_due(24, 500, null)").fetchall()
        assert stale and (u,) in [tuple(r) for r in due]
        rewritten = await export_user(app_state.engine, app_state.vault, b, ref)
        assert rewritten.uploaded and rewritten.items < done.items
        # "Delete what Vanimo learned": the job removes the snapshot at once.
        assert (await client.delete("/api/learning", headers=h)).status_code in (200, 202)
        await _settle(app_state)
        assert key_for(ref) not in store.objects
    finally:
        b.macie_mode, b.snapshot_store = "offline", None


async def test_failed_snapshot_delete_leaves_it_due(
    client: httpx.AsyncClient, database: dict[str, str], settings: Settings, app_state: AppState
) -> None:
    from vanimo.backstops.snapshots import forget

    _, item = await _learned_user(client, database, settings)
    with _owner(database) as conn:
        row = conn.execute("select tenant_id, owner_user_id from vanimo.l1_items where id = %s", (item,)).fetchone()
    ref = UserRef(row[0], row[1])
    await export_user(app_state.engine, app_state.vault, app_state.backstops, ref)  # a snapshot row exists
    store = FakeStore()
    store.fail_delete = True
    b = Backstops(pii=OfflinePiiDetector(), guardrail=OfflineGuardrail(), macie_mode="aws", snapshot_store=store)
    await forget(app_state.engine, b, ref)
    with _owner(database) as conn:
        stale, stored = conn.execute(
            "select changes > exported_changes, stored from vanimo.l1_snapshots where owner_user_id = %s",
            (ref.user_id,),
        ).fetchone()
    assert stale and stored is True  # due on the next sweep, which rewrites or deletes it


async def test_aws_macie_findings_are_recorded_once_and_pause(
    client: httpx.AsyncClient, database: dict[str, str], settings: Settings, app_state: AppState
) -> None:
    admin = await _user(client, database, settings, role="admin")
    with _owner(database) as conn:
        t, u = conn.execute("select tenant_id, id from vanimo.users order by created_at desc limit 1").fetchone()

    class Reader:
        async def findings(self, since_ms: int) -> list[MacieFinding]:
            return [MacieFinding("macie-test-" + uuid.uuid4().hex[:6], UserRef(t, u), {"NAME": 1}, "medium")]

    b = app_state.backstops
    b.macie_mode, b.macie_reader = "aws", Reader()
    try:
        assert await poll_round(app_state.engine, b, force=True) == 1
        assert await poll_round(app_state.engine, b) == 0  # polled again only after 15 minutes
        status = (await client.get("/api/admin/backstops", headers=admin)).json()
        assert status["paused"]["reason"] == "macie_finding" and status["paused"]["ref"].startswith("macie-test-")
    finally:
        b.macie_mode, b.macie_reader = "offline", None
        await client.post("/api/admin/backstops/resume", headers=admin)


async def test_backstop_outage_fails_the_learning_run_without_storing(
    client: httpx.AsyncClient, database: dict[str, str], settings: Settings, app_state: AppState
) -> None:
    h = await _user(client, database, settings)
    assert (await client.post("/api/controls/scan", headers=h)).status_code == 202
    assert (await client.post("/api/controls/review", json={"outcome": "finished"}, headers=h)).status_code == 200
    b = current()
    assert b is app_state.backstops  # installed at startup
    real, b.pii = b.pii, Down()
    try:
        run = (await client.post("/api/learning/run", headers=h)).json()["run"]
    finally:
        b.pii = real
    assert run["status"] == "failed" and run["errorCode"] == "pii_backstop_unavailable"
    items = (await client.get("/api/learning/items", headers=h)).json()["items"]
    assert items == []


async def test_guardrail_blocks_are_recorded_for_the_acting_user(
    client: httpx.AsyncClient, database: dict[str, str], settings: Settings, app_state: AppState
) -> None:
    admin = await _user(client, database, settings, role="admin")
    with _owner(database) as conn:
        t, u = conn.execute("select tenant_id, id from vanimo.users order by created_at desc limit 1").fetchone()
    token = backstop_events.ACTING_USER.set(UserRef(t, u))
    try:
        await app_state._guardrail_blocked(GuardrailBlocked("OUTPUT", {"NAME": 2}))
    finally:
        backstop_events.ACTING_USER.reset(token)
    events = (await client.get("/api/admin/backstops", headers=admin)).json()["events"]
    ev = next(e for e in events if e["source"] == "guardrail")
    assert ev["stage"] == "model_output" and ev["kinds"] == {"NAME": 2} and ev["user"] == str(u)


async def test_probe_uses_synthetic_text_and_reports_each_service(
    client: httpx.AsyncClient, database: dict[str, str], settings: Settings
) -> None:
    admin = await _user(client, database, settings, role="admin")
    out = {p["key"]: p for p in (await client.post("/api/admin/backstops/probe", headers=admin)).json()}
    assert out["comprehend"]["state"] == "ok" and out["guardrail"]["code"] == "blocked"
    assert out["guardrail_india"]["state"] == "ok"  # each Indian identifier alone is blocked too
    assert out["macie"]["code"] == "offline"


# --- the Macie job (operator script) ------------------------------------------------------------
class FakeMacie:
    def __init__(self, *, matches: bool = True, existing: bool = False, false_positive: bool = False) -> None:
        self.matches = matches
        self.false_positive = false_positive
        self.existing = existing
        self.created: list[dict] = []
        self.cancelled: list[str] = []

    def list_custom_data_identifiers(self, **kw: Any) -> dict:
        names = ["aadhaar", "pan", "gstin", "ifsc", "upi", "voter-id"]
        return {"items": [{"name": f"vanimo-in-dev-{n}", "id": f"id-{n}"} for n in names] + [{"name": "x", "id": "x"}]}

    def get_custom_data_identifier(self, id: str) -> dict:
        return {"regex": "x", "keywords": ["voter"] if id == "id-voter-id" else None}

    def test_custom_data_identifier(self, **kw: Any) -> dict:
        from vanimo.ops.macie_job import CLEAN_LINE

        if kw["sampleText"] == CLEAN_LINE:
            return {"matchCount": 1 if self.false_positive else 0}
        return {"matchCount": 1 if self.matches else 0}

    def list_classification_jobs(self, **kw: Any) -> dict:
        return {"items": [{"jobId": "job-1", "jobStatus": "RUNNING"}] if self.existing else []}

    def update_classification_job(self, jobId: str, jobStatus: str) -> None:
        self.cancelled.append(jobId)

    def create_classification_job(self, **kw: Any) -> dict:
        self.created.append(kw)
        return {"jobId": "job-2"}


def test_macie_job_is_daily_scoped_and_uses_our_identifiers() -> None:
    from vanimo.ops import macie_job

    fake = FakeMacie()
    ids = macie_job.find_identifiers(fake, "vanimo-in-dev")
    assert set(ids) == set(macie_job.SAMPLES) and macie_job.test_identifiers(fake, ids) == []
    macie_job.create_job(fake, account="123", bucket="snap", name="n", identifier_ids=sorted(ids.values()))
    job = fake.created[0]
    assert job["jobType"] == "SCHEDULED" and job["scheduleFrequency"] == {"dailySchedule": {}}
    assert job["initialRun"] is True and job["managedDataIdentifierSelector"] == "RECOMMENDED"
    assert job["s3JobDefinition"]["bucketDefinitions"] == [{"accountId": "123", "buckets": ["snap"]}]
    assert len(job["customDataIdentifierIds"]) == 6 and "x" not in job["customDataIdentifierIds"]
    assert macie_job.test_identifiers(FakeMacie(matches=False), ids) == sorted(macie_job.SAMPLES, key=list(ids).index)
    assert macie_job.existing_job(FakeMacie(existing=True), "n") == {"jobId": "job-1", "jobStatus": "RUNNING"}
    assert "pan(false positive)" in macie_job.test_identifiers(FakeMacie(false_positive=True), ids)


# --- F12: replacing names is each user's choice -------------------------------------------------------
async def test_names_stay_unless_the_user_chose_to_replace_them() -> None:
    def find(t: str) -> list[Finding]:
        return [at(t, "Arjun Mehta", "NAME")] if "Arjun Mehta" in t else []

    text = "Meera, ask Arjun Mehta for the PAN ABCPE1234F, thanks Siddharth"
    g = Gazetteer(me=Person("Siddharth Kalyani", "siddharth.kalyani@intuitive.ai"))
    g.add("Meera Iyer", "meera.iyer@kestrel.example")
    kept = await Redactor(Matcher([], redact_names=False), g, _hasher, pii=Fixed(find)).redact(text)
    assert "Meera" in kept.text and "Arjun Mehta" in kept.text and "Siddharth" in kept.text
    assert "[PAN]" in kept.text and "ABCPE1234F" not in kept.text  # identifiers are masked either way
    replaced = await Redactor(Matcher([], redact_names=True), g, _hasher, pii=Fixed(find)).redact(text)
    assert "Meera" not in replaced.text and "Arjun" not in replaced.text and "⟦ME⟧" in replaced.text


async def test_guardrail_blocks_names_only_for_users_who_replace_them() -> None:
    from vanimo.backstops.guardrail import BLOCK_NAMES

    reported = {
        "action": "NONE",
        "assessments": [
            {
                "sensitiveInformationPolicy": {
                    "piiEntities": [{"type": "NAME", "match": "Arjun", "action": "NONE", "detected": True}]
                }
            }
        ],
    }
    fake = FakeBedrock(reported)
    g = BedrockGuardrail("g", "1", "ap-south-1", client=fake)
    token = BLOCK_NAMES.set(False)
    try:
        await g.check("INPUT", ["Hi Arjun"])  # names kept by choice: a name is no finding
    finally:
        BLOCK_NAMES.reset(token)
    with pytest.raises(GuardrailBlocked) as caught:
        await g.check("INPUT", ["Hi Arjun"])  # default (and users who replace names): blocked
    assert caught.value.kinds == {"NAME": 1} and fake.calls[0]["outputScope"] == "FULL"


async def test_name_choice_is_off_by_default_and_set_on_the_learning_page(
    client: httpx.AsyncClient, database: dict[str, str], settings: Settings, app_state: AppState
) -> None:
    h = await _user(client, database, settings, redact_names=False)
    assert (await client.get("/api/learning", headers=h)).json()["redactNames"] is False
    assert (await client.post("/api/controls/scan", headers=h)).status_code == 202
    assert (await client.post("/api/controls/review", json={"outcome": "finished"}, headers=h)).status_code == 200
    run = await client.post("/api/learning/run", headers=h)
    assert run.json()["run"]["counts"]["names_redacted"] == 0
    with _owner(database) as conn:
        rows = conn.execute(
            "select i.tenant_id, i.owner_user_id, i.text_enc from vanimo.l1_items i where i.run_id = %s",
            (run.json()["run"]["id"],),
        ).fetchall()
    texts = [app_state.vault.decrypt_user(t, u, x, "l1_text") or "" for t, u, x in rows]
    assert texts and not any("⟦PERSON_" in x for x in texts)  # names left as written
    assert not any("⟦ME" in x for x in texts)
    # Turning it on: what's stored was learned the other way, so the page asks for a new run.
    on = (await client.put("/api/learning/names", json={"redactNames": True}, headers=h)).json()
    assert on["redactNames"] is True and on["namesOutOfDate"] is True
    again = await client.post("/api/learning/run", headers=h)
    assert again.json()["run"]["counts"]["names_redacted"] == 1
    assert (await client.get("/api/learning", headers=h)).json()["namesOutOfDate"] is False
