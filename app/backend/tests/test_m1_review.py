"""Regression tests for the M1 review findings."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import TENANT
from tests.helpers import _find, _settle, _sources, _user
from vanimo.api import deps
from vanimo.config import Settings
from vanimo.controls.index import load_index
from vanimo.controls.scan import run_scan
from vanimo.controls.store import load_engine
from vanimo.db.session import provision_user, user_tx
from vanimo.graph.client import GraphClient
from vanimo.sources.base import Address, Chat
from vanimo.sources.graph import GraphSource
from vanimo.sources.sample import SampleSource
from vanimo.state import AppState
from vanimo.vault import Vault

pytestmark = pytest.mark.db
GRAPH = "https://graph.microsoft.com/v1.0"


def _recips(*emails: str) -> list[dict]:
    return [{"emailAddress": {"address": e, "name": e.split("@")[0].title()}} for e in emails]


@pytest.fixture
def mocked_graph() -> respx.MockRouter:
    with respx.mock(assert_all_called=False) as r:
        r.get(f"{GRAPH}/me").mock(
            return_value=httpx.Response(200, json={"displayName": "Me", "mail": "Me@Contoso.example"})
        )
        r.get(f"{GRAPH}/organization").mock(
            return_value=httpx.Response(200, json={"value": [{"verifiedDomains": [{"name": "contoso.example"}]}]})
        )
        delta = f"{GRAPH}/me/mailFolders/sentitems/messages/delta"
        r.get(delta, params={"skip": "1"}).mock(
            return_value=httpx.Response(200, json={"@odata.deltaLink": "d", "value": [
                # The same message again (delta paging can repeat): counted once, no abort.
                {"id": "m1", "conversationId": "c1", "subject": "Kickoff", "sentDateTime": "2026-10-01T10:00:00Z",
                 "toRecipients": _recips("ann@fabrikam.example")},
                {"id": "m2", "conversationId": "c1", "subject": "Re: Kickoff", "sentDateTime": "2026-10-02T10:00:00Z",
                 "toRecipients": _recips("ann@fabrikam.example"), "ccRecipients": _recips("me@contoso.example"),
                 "from": {"emailAddress": {"address": "boss@contoso.example", "name": "Boss"}}},
                {"id": "m3", "@removed": {"reason": "deleted"}},
            ]})
        )  # fmt: skip
        r.get(delta).mock(
            return_value=httpx.Response(200, json={"@odata.nextLink": f"{delta}?skip=1", "value": [
                {"id": "m1", "conversationId": "c1", "subject": "Kickoff", "sentDateTime": "2026-10-01T10:00:00Z",
                 "toRecipients": _recips("ann@fabrikam.example", "ann@fabrikam.example")},
            ]})
        )  # fmt: skip
        big = [{"email": f"p{i}@contoso.example", "displayName": f"P{i}"} for i in range(25)]
        r.get(f"{GRAPH}/chats/chat-big/members").mock(
            return_value=httpx.Response(200, json={"value": [*big, {"email": "p25@contoso.example"}]})
        )
        r.get(f"{GRAPH}/me/chats").mock(
            return_value=httpx.Response(200, json={"value": [
                {"id": "chat-1", "chatType": "oneOnOne", "members": [{"email": "me@contoso.example"},
                                                                    {"email": "ann@fabrikam.example"}]},
                {"id": "chat-big", "chatType": "group", "topic": "Everyone", "viewpoint": {"isHidden": True},
                 "members": big},
                {"id": "chat-1", "chatType": "oneOnOne", "members": [{"email": "ann@fabrikam.example"}]},
            ]})
        )  # fmt: skip
        r.get(f"{GRAPH}/me/calendarView").mock(
            return_value=httpx.Response(200, json={"value": [
                {"id": "e1", "subject": "Weekly", "start": {"dateTime": "2026-10-05T10:00:00.0000000"},
                 "end": {"dateTime": "2026-10-05T11:00:00.0000000"}, "seriesMasterId": "s1",
                 "organizer": {"emailAddress": {"address": "me@contoso.example"}}, "isOrganizer": True,
                 "attendees": _recips("ann@fabrikam.example"), "sensitivity": "private"},
            ]})
        )  # fmt: skip
        yield r


async def test_graph_source_scan_matches_the_sample_contract(
    database: dict[str, str], settings: Settings, mocked_graph: respx.MockRouter
) -> None:
    engine = create_async_engine(database["app"])
    vault = Vault(settings.vault_master_key.get_secret_value())
    ref = await provision_user(engine, entra_tenant_id=TENANT, entra_oid=str(uuid.uuid4()), cell="in", data_region="IN")
    source = GraphSource(GraphClient("tok", httpx.AsyncClient()))
    counts = await run_scan(engine, vault, ref, source)
    assert (counts["messages"], counts["threads"], counts["chats"], counts["meetings"]) == (2, 1, 2, 1)

    # Every $select is metadata-only; chats were never asked for message previews.
    for call in mocked_graph.calls:
        params = str(call.request.url.params).lower()
        assert "body" not in params and "lastmessagepreview" not in params
    async with user_tx(engine, ref) as conn:
        view = await load_index(conn, vault, ref)
    emails = {p.email for p in view.people.values()}
    assert "me@contoso.example" not in emails  # you are never one of your own sources
    assert "boss@contoso.example" in emails  # sent on behalf of: a participant
    ann = next(p for p in view.people.values() if p.email == "ann@fabrikam.example")
    assert ann.sent == 2 and not ann.internal  # deduped per message
    big = next(c for c in view.chats.values() if c.label == "Everyone")
    assert big.members == 26 and big.hidden  # members re-fetched beyond Graph's 25
    meeting = next(iter(view.meetings.values()))
    assert meeting.private and meeting.series_hash
    # Organisation domains are recorded tenant-wide.
    async with user_tx(engine, ref) as conn:
        eng = await load_engine(conn, vault, ref)
    assert eng.org_domains == {vault.key_hash(ref.tenant_id, "domain", "contoso.example")}
    await engine.dispose()


async def test_domain_rule_honours_unticked_chats(client: httpx.AsyncClient, scanned: dict) -> None:
    domains = await _sources(client, scanned, "domains")
    kestrel = _find(domains, "kestrel.example")
    impact = (await client.post("/api/controls/impact", json={"kind": "domain", "id": kestrel["id"]},
                                headers=scanned)).json()  # fmt: skip
    big = next(c for c in impact["chatList"] if c["label"] == "All Kestrel India")
    resp = await client.post("/api/controls/rules", headers=scanned,
                             json={"kind": "domain", "id": kestrel["id"], "exceptChatIds": [big["id"]]})  # fmt: skip
    assert resp.status_code == 201
    chats = await _sources(client, scanned, "chats")
    assert not _find(chats, "All Kestrel India")["excluded"]
    assert _find(chats, "Delivery leads")["excluded"]


async def test_domain_impact_counts_subdomains_and_use_again_targets_the_right_rule(
    client: httpx.AsyncClient, scanned: dict
) -> None:
    domains = await _sources(client, scanned, "domains")
    parent = _find(domains, "bluefinbank.example")
    impact = (await client.post("/api/controls/impact", json={"kind": "domain", "id": parent["id"]},
                                headers=scanned)).json()  # fmt: skip
    sub_id = _find(domains, "cards.bluefinbank.example")["id"]
    deepa_only = (
        await client.post("/api/controls/impact", headers=scanned, json={"kind": "domain", "id": sub_id})
    ).json()
    assert impact["emails"] > deepa_only["emails"] > 0  # parent covers the subdomain too
    await client.post("/api/controls/rules", json={"kind": "domain", "id": parent["id"]}, headers=scanned)
    domains = await _sources(client, scanned, "domains")
    assert _find(domains, "bluefinbank.example")["ruleId"]
    sub = _find(domains, "cards.bluefinbank.example")
    assert sub["excluded"] and sub["ruleId"] is None and sub["via"] == ["bluefinbank.example"]


class _SlowSample(SampleSource):
    """Pauses the header pass after the mail headers, so a word can be added mid-scan."""

    def __init__(self, email: str | None, gate: asyncio.Event, reached: asyncio.Event) -> None:
        super().__init__(email)
        self.gate, self.reached = gate, reached

    async def chats(self) -> AsyncIterator[Chat]:
        self.reached.set()
        await self.gate.wait()
        async for c in super().chats():
            yield c


async def test_word_added_during_a_scan_is_masked_in_the_new_index(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState
) -> None:
    session = (await client.get("/api/auth/session", headers=scanned)).json()
    gate, reached = asyncio.Event(), asyncio.Event()
    original = deps.get_source

    async def slow_source(principal: deps.CurrentPrincipal) -> SampleSource:
        return _SlowSample(session["email"], gate, reached)

    client._transport.app.dependency_overrides[original] = slow_source  # type: ignore[attr-defined]
    try:
        scan = asyncio.create_task(client.post("/api/controls/scan", headers=scanned))
        await reached.wait()
        added = await client.post("/api/controls/never-send", json={"text": "Falcon", "kind": "codename"},
                                  headers=scanned)  # fmt: skip
        assert added.status_code == 201
        # Wait for the scrub job only (the scan task is deliberately paused): it runs on the *old* index.
        for _ in range(200):
            receipts = (await client.get("/api/controls/receipts", headers=scanned)).json()
            if receipts and receipts[0]["reason"] == "term_added" and receipts[0]["status"] == "done":
                break
            await asyncio.sleep(0.05)
        else:
            pytest.fail("scrub job never finished")
        gate.set()
        assert (await scan).status_code == 202
    finally:
        client._transport.app.dependency_overrides.clear()  # type: ignore[attr-defined]
    threads = await _sources(client, scanned, "threads")
    assert threads and not any("falcon" in t["label"].lower() for t in threads)


async def test_cannot_remove_another_users_rules_or_words(
    client: httpx.AsyncClient, database: dict[str, str], settings: Settings, scanned: dict
) -> None:
    person = _find(await _sources(client, scanned, "people"), "Meera Iyer")
    rule = (
        await client.post("/api/controls/rules", json={"kind": "person", "id": person["id"]}, headers=scanned)
    ).json()
    word = (await client.post("/api/controls/never-send", json={"text": "Monsoon"}, headers=scanned)).json()
    other = await _user(client, database, settings)
    assert (await client.delete(f"/api/controls/rules/{rule['id']}", headers=other)).status_code == 404
    assert (await client.delete(f"/api/controls/never-send/{word['id']}", headers=other)).status_code == 404
    assert (await client.patch(f"/api/controls/never-send/{word['id']}", json={"allowInDrafts": True},
                               headers=other)).status_code == 404  # fmt: skip
    assert len((await client.get("/api/controls/rules", headers=scanned)).json()) == 1


async def test_approved_only_never_excludes_colleagues_even_without_a_scan(
    client: httpx.AsyncClient, database: dict[str, str], settings: Settings, scanned: dict, app_state: AppState
) -> None:
    newcomer = await _user(client, database, settings)  # same local tenant, never scanned
    session = (await client.get("/api/auth/session", headers=newcomer)).json()
    assert session["email"]
    from vanimo.auth.local import resolve_session

    principal = await resolve_session(app_state.engine, newcomer["Authorization"].split()[1])
    ref = principal.local_user
    async with user_tx(app_state.engine, ref) as conn:
        engine = await load_engine(conn, app_state.vault, ref)
    engine.external_mode = "approved_only"
    # The scanned user's scan recorded kestrel.example for the whole tenant.
    assert not engine.person_reasons(Address("meera.iyer@kestrel.example"))
    assert engine.person_reasons(Address("emily.park@orionhealth.example"))


async def test_never_send_words_are_gone_from_every_decrypted_index_field(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState
) -> None:
    await client.post("/api/controls/never-send", json={"text": "Falcon", "kind": "codename"}, headers=scanned)
    await _settle(app_state)
    principal_email = (await client.get("/api/auth/session", headers=scanned)).json()["email"]
    from vanimo.auth.local import resolve_session

    ref = (await resolve_session(app_state.engine, scanned["Authorization"].split()[1])).local_user
    async with user_tx(app_state.engine, ref) as conn:
        view = await load_index(conn, app_state.vault, ref)
    stored = [p.name or "" for p in view.people.values()] + [t.subject or "" for t in view.threads.values()]
    stored += [c.label for c in view.chats.values()] + [m.subject or "" for m in view.meetings.values()]
    assert principal_email and stored
    assert not any("falcon" in s.lower() for s in stored)
    assert any("⟦NS_" in s for s in stored)


async def test_review_of_sample_data_does_not_unlock_graph(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState
) -> None:
    done = await client.post("/api/controls/review", json={"outcome": "finished"}, headers=scanned)
    assert done.json()["onboardingState"] == "review_done"
    from vanimo.auth.local import resolve_session
    from vanimo.gates import ReviewPending, require_review_done

    ref = (await resolve_session(app_state.engine, scanned["Authorization"].split()[1])).local_user
    await require_review_done(app_state.engine, ref, "sample")
    with pytest.raises(ReviewPending):
        await require_review_done(app_state.engine, ref, "graph")


async def test_sweeper_resumes_jobs_and_fails_stale_scans(
    client: httpx.AsyncClient, scanned: dict, app_state: AppState, database: dict[str, str]
) -> None:
    import psycopg

    from vanimo.controls.sweeper import sweep_once

    owner = database["owner"].replace("postgresql+psycopg://", "postgresql://")
    await client.post("/api/controls/never-send", json={"text": "Monsoon"}, headers=scanned)
    await _settle(app_state)
    with psycopg.connect(owner) as conn:
        conn.execute("update vanimo.purge_jobs set status = 'pending', requested_at = now() - interval '1 hour'")
        conn.execute(
            "insert into vanimo.source_scans (tenant_id, owner_user_id, source_kind, status, started_at) "
            "select tenant_id, owner_user_id, 'sample', 'running', now() - interval '2 hours' "
            "from vanimo.purge_jobs limit 1"
        )
    failed, resumed = await sweep_once(app_state.engine, app_state.vault)
    assert failed >= 1 and resumed >= 1
    with psycopg.connect(owner) as conn:
        assert conn.execute("select count(*) from vanimo.purge_jobs where status = 'pending'").fetchone() == (0,)
