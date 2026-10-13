"""Unit tests: the never-send matcher and the exclusion engine (no database)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from vanimo.controls.engine import ExclusionEngine, UserRule
from vanimo.controls.neversend import Matcher, Term, normalise, render_removed, variants
from vanimo.sources.base import Address, Chat, Event, SentHeader


def _m(*terms: Term) -> Matcher:
    return Matcher(list(terms))


FALCON = Term("0000000a", "Falcon", "codename")
SHARMA = Term("0000000b", "Sharma", "name", ("शर्मा",))
MONSOON = Term("0000000c", "Monsoon", "word")


@pytest.mark.parametrize(
    "text",
    [
        "Project Falcon timeline",
        "project-falcon kickoff",
        "PROJECTFALCON notes",
        "Fal​con budget",  # zero-width space inside
        "Fal‮con",  # bidi override inside
        "Ｆａｌｃｏｎ deck",  # full-width
        "Fаlcon",  # Cyrillic а
        "FALCON-2 plan",
        "Falconry club",  # codename: substring, whole word masked
    ],
)
def test_codename_variants_are_caught(text: str) -> None:
    masked, hits = _m(FALCON).mask(text)
    assert hits == 1, text
    assert "alcon" not in render_removed(masked).lower()


@pytest.mark.parametrize(
    "text",
    ["Sharma-ji will join", "Sharmaji ne bola", "Sharma's laptop", "Mrs Sharmaa called", "Sharrma ji", "शर्मा जी आए"],
)
def test_names_with_honorifics_hinglish_and_devanagari(text: str) -> None:
    masked, hits = _m(SHARMA).mask(text)
    assert hits == 1 and "[removed]" in render_removed(masked), text


@pytest.mark.parametrize("text", ["Sharmila is fine", "monsoonal rains", "nothing here"])
def test_word_boundaries_avoid_false_hits(text: str) -> None:
    assert _m(SHARMA, MONSOON).mask(text) == (text, 0)


def test_devanagari_boundaries_keep_matras_attached() -> None:
    term = Term("0000000d", "किताब", "word")
    assert _m(term).count("हिंदी किताब") == 1
    assert _m(term).count("किताबें") == 0  # a longer word, not a hit on "word" kind


def test_placeholder_and_offsets_survive_normalisation() -> None:
    masked, hits = _m(MONSOON, FALCON).mask("x Ｍｏｎｓｏｏｎ and fal​con y")
    assert hits == 2
    assert masked == "x ⟦NS_0000000c⟧ and ⟦NS_0000000a⟧ y"
    assert render_removed(masked) == "x [removed] and [removed] y"


def test_normalise_devanagari_digits_and_whitespace() -> None:
    shadow, _ = normalise("Room  १२३\tA")
    assert shadow == "room 123 a"


def test_variants_offered_for_confirmation() -> None:
    v = variants("Project Falcon", "codename")
    assert v[:4] == ["project falcon", "project-falcon", "project_falcon", "projectfalcon"]
    assert "project falcons" in v


def test_empty_matcher_is_a_no_op() -> None:
    assert not Matcher([])
    assert Matcher([]).mask("anything") == ("anything", 0)


# --- engine --------------------------------------------------------------------------------


def _hasher(kind: str, value: str) -> str:
    return f"{kind}:{value.lower()}"


NOW = datetime(2026, 10, 13, tzinfo=UTC)
ME = Address("me@kestrel.example", "Me")
RAHUL = Address("rahul@kestrel.example", "Rahul")
KARAN = Address("karan@bluefinbank.example", "Karan")
DEEPA = Address("deepa@cards.bluefinbank.example", "Deepa")
JOHN = Address("john@acmeretail.example", "John")


def _engine(**kw: object) -> ExclusionEngine:
    return ExclusionEngine(hasher=_hasher, self_email=ME.email, org_domains=frozenset({"domain:kestrel.example"}),
                           **kw)  # type: ignore[arg-type]  # fmt: skip


def test_person_rule_covers_mail_chats_and_meetings_except_unticked_chats() -> None:
    rule = UserRule("r1", "person", "person:rahul@kestrel.example", frozenset({"chat:big"}))
    e = _engine(user_rules=[rule])
    assert e.message(SentHeader("m", "c", "s", NOW, to=(RAHUL,))).excluded
    assert e.chat(Chat("small", "group", None, (ME, RAHUL))).excluded
    assert not e.chat(Chat("big", "group", "All hands", (ME, RAHUL))).excluded  # unticked (D5)
    assert e.meeting(Event("e", "x", NOW, NOW, organizer=RAHUL)).excluded
    assert not e.message(SentHeader("m2", "c2", "s", NOW, to=(JOHN,))).excluded


def test_domain_rule_includes_subdomains() -> None:
    e = _engine(user_rules=[UserRule("r", "domain", "domain:bluefinbank.example")])
    assert e.message(SentHeader("m", "c", None, NOW, cc=(DEEPA,))).excluded
    assert not e.message(SentHeader("m", "c", None, NOW, to=(JOHN,))).excluded


def test_thread_chat_meeting_and_series_rules() -> None:
    e = _engine(user_rules=[
        UserRule("t", "thread", "thread:conv-1"), UserRule("c", "chat", "chat:chat-1"),
        UserRule("m", "meeting", "meeting:evt-1"), UserRule("s", "series", "series:ser-1"),
    ])  # fmt: skip
    assert e.message(SentHeader("m", "conv-1", None, NOW)).excluded
    assert e.chat(Chat("chat-1", "oneOnOne", None, (ME, JOHN))).excluded
    assert e.meeting(Event("evt-1", None, NOW, NOW, None)).excluded
    assert e.meeting(Event("evt-9", None, NOW, NOW, None, series_id="ser-1")).excluded
    assert not e.meeting(Event("evt-2", None, NOW, NOW, None)).excluded


def test_organisation_rules_win_and_are_marked_tenant() -> None:
    e = _engine(excluded_domains={"domain:bluefinbank.example": "acct-1"})
    d = e.message(SentHeader("m", "c", None, NOW, to=(RAHUL, DEEPA)))
    assert d.excluded and d.by_tenant and d.reasons[0].account_id == "acct-1"


def test_approved_only_mode() -> None:
    e = _engine(external_mode="approved_only", approved_domains=frozenset({"domain:acmeretail.example"}))
    assert not e.message(SentHeader("m", "c", None, NOW, to=(JOHN, RAHUL))).excluded  # approved + internal
    blocked = e.message(SentHeader("m", "c", None, NOW, to=(JOHN, KARAN)))
    assert blocked.excluded and blocked.reasons[0].kind == "not_approved"
    assert not e.message(SentHeader("m", "c", None, NOW, to=(ME,))).excluded  # you are never a reason
