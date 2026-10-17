"""M6 review fixes: unknown speakers' names redacted, terminal transcript errors, token clean-up scope,
retention isolated from purges, weekday words, first names as words."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx

from tests.helpers import _user
from tests.test_learning import _review
from tests.test_m5 import IST
from tests.test_m6 import WED, _meeting, _scan, _scan_all
from vanimo.api import deps
from vanimo.config import Settings
from vanimo.controls.engine import ExclusionEngine
from vanimo.controls.neversend import Matcher
from vanimo.drafting.context import Directory, build_redactor
from vanimo.memory import ask as asking
from vanimo.memory import ingest
from vanimo.memory.when import resolve
from vanimo.redaction.pipeline import Person
from vanimo.sources.base import Address, Cue, Event, Transcript, TranscriptRef, TranscriptsUnavailable
from vanimo.sources.sample import SampleSource
from vanimo.state import AppState


def _hasher(kind: str, value: str) -> str:
    import hashlib

    return hashlib.sha256(f"{kind}:{value}".encode()).hexdigest()


def test_unknown_speakers_are_left_out_but_their_names_are_redacted() -> None:
    me = Address("me@kestrel.example", "Sid K")
    lisa = Address("lisa.chen@acme.example", "Lisa Chen")
    start = datetime(2026, 10, 13, 4, 30, tzinfo=UTC)
    event = Event("e1", "Sync", start, start + timedelta(hours=1), me, attendees=(lisa,), is_online=True)
    ref = TranscriptRef("t1", "m1", start)
    cues = (
        Cue(0, 1000, "Jordan Lee (Guest)", "Sorry, joining late from the store team."),
        Cue(5000, 6000, "Lisa Chen", "Thanks Jordan, we need the rollback tested."),
    )
    directory = Directory(Person("Sid K", me.email), None, frozenset(), frozenset({"kestrel.example"}), ())
    roster = ingest.Roster(me)
    roster.add(me)
    roster.add(lisa)
    result = ingest.IngestResult()
    built = ingest.build(
        event, [Transcript(ref, True, cues)], roster=roster, known={}, directory=directory,
        redactor_for=lambda people: build_redactor(Matcher([]), _hasher, directory, [lisa, *people]),
        ex_engine=ExclusionEngine(_hasher), org_domains=frozenset({"kestrel.example"}), result=result,
    )  # fmt: skip
    assert result.counts["unknown_speaker"] == 1 and len(built.turns) == 1
    said = built.turns[0].text
    assert "Jordan" not in said and "store team" not in said and "⟦PERSON_" in said
    assert "Jordan Lee" not in {a.name for a in built.people.values()}  # never part of the lineage


async def test_terminal_transcript_errors_are_not_retried(client: httpx.AsyncClient, scanned: dict) -> None:
    h = scanned
    await _review(client, h)
    calls: list[str] = []

    class TooLarge(SampleSource):
        async def transcript(self, ref: TranscriptRef) -> Transcript:
            calls.append(ref.id)
            raise TranscriptsUnavailable("too_large")

    async def source(principal: deps.CurrentPrincipal) -> SampleSource:
        return TooLarge(principal.email)

    client._transport.app.dependency_overrides[deps.get_source] = source  # type: ignore[attr-defined]
    try:
        await _scan_all(client, h)
        first = len(calls)
        await _scan_all(client, h)
    finally:
        client._transport.app.dependency_overrides.clear()  # type: ignore[attr-defined]
    assert first == 5 and len(calls) == first  # each read once, never again


async def test_retention_failure_never_blocks_purges(app_state: AppState, monkeypatch: object) -> None:
    from vanimo.controls import sweeper

    calls: list[str] = []
    real = sweeper.text

    def spy(sql: str):  # type: ignore[no-untyped-def]
        calls.append(sql)
        if "expire_meeting_memory" in sql:
            return real("select * from vanimo_private.no_such_function()")
        return real(sql)

    monkeypatch.setattr(sweeper, "text", spy)  # type: ignore[attr-defined]
    await sweeper.sweep_once(app_state.engine, app_state.vault)  # doesn't raise: purges were claimed
    assert any("claim_purge_jobs" in c for c in calls)


def test_weekday_and_name_words_need_capitals() -> None:
    lookback = timedelta(days=30)
    assert resolve("what did we say when we sat with the client?", WED, IST, lookback=lookback).day is None
    assert resolve("decisions on Sat", WED, IST, lookback=lookback).day is not None
    names = {"⟦PERSON_aaaaaaaa": "Will Smith", "⟦PERSON_bbbbbbbb": "Lisa Chen"}
    assert asking.parse_question("what will we do about the cutover?", WED, IST, names).people == set()
    assert asking.parse_question("What did Will ask for?", WED, IST, names).people == {"⟦PERSON_aaaaaaaa"}
    assert asking.parse_question("what did lisa chen say?", WED, IST, names).people == {"⟦PERSON_bbbbbbbb"}


async def test_unknown_guest_names_never_stored_in_clear(
    client: httpx.AsyncClient, scanned: dict, database: dict, settings: Settings
) -> None:
    h = scanned
    await _review(client, h)
    await _scan_all(client, h)
    latest = await _meeting(client, h, "Acme weekly sync", 0)
    assert all(t["speaker"] != "Jordan Lee" for t in latest["transcript"])
    assert (await _scan(client, h))["stored"] == 0
    assert await _user(client, database, settings)  # other users see nothing of it (RLS covered in test_rls)
