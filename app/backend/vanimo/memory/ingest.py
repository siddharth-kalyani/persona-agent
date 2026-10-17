"""Meeting memory ingestion: Teams transcripts → episodes → memory atoms (MVP plan M6).

There is no background Graph token yet (no refresh tokens, no change notifications), so this runs
when the user opens the Meetings tab, like M4's matching and M5's commitments scan. The order is the
learner's (§6.5 X2), with the calendar as the header pass:

  1. the onboarding gate for this source, and the organisation's meeting-memory switch;
  2. calendar metadata only: Teams meetings of the last 30 days that ended, organised inside the
     organisation (Graph has no transcripts of other companies' meetings), not private, and allowed
     by the exclusion engine (occurrence, series, every invitee and their domains, client scoping).
     An excluded meeting's transcripts are never listed or fetched;
  3. the meeting's transcript list (a series shares one: an occurrence takes those that started in
     its own time), then the text, in memory (L0);
  4. speakers matched to the invite by name (Teams' attribution). Words of someone not on the invite
     are left out (nobody can check them against your rules), and if that someone is a person you
     excluded, the whole meeting is. Each turn is redacted to L1; a turn that can't be is left out;
  5. atoms found in L1 (offline rules or Claude), and your own promises go to the commitments
     ledger; all of it stored under the controls lock if the controls didn't change meanwhile.

Stored: the L1 turns for 30 days (citations), the atoms for 12 months, lineage, and a content-free
record of each meeting's outcome (so a meeting is read once, and one you deleted is never read again).
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from vanimo.commitments import store as ledger
from vanimo.commitments.extract import Found
from vanimo.controls.store import hasher_for, load_engine, load_matcher, lock_user_controls
from vanimo.db.session import UserRef, user_tx
from vanimo.drafting.context import Directory, build_redactor
from vanimo.gates import require_review_done
from vanimo.learning import labels
from vanimo.learning.backfill import controls_version
from vanimo.logs import get_logger
from vanimo.memory import vtt
from vanimo.memory.atoms import OfflineAtomExtractor, Turn
from vanimo.redaction.marks import L1_MARKS, TOKEN
from vanimo.redaction.pipeline import Person, RedactionBlocked, Redactor
from vanimo.sources.base import Address, Event, Transcript, TranscriptRef, TranscriptsUnavailable, WorkspaceSource
from vanimo.state import AppState

log = get_logger("vanimo.memory")

LOOKBACK = timedelta(days=30)
SETTLE = timedelta(minutes=5)  # transcripts appear after the meeting ends (no SLA from Microsoft)
NO_TRANSCRIPT_RETRY_FOR = timedelta(days=2)  # keep looking this long after the end, then stop
RECHECK_EVERY = timedelta(minutes=15)
UNAVAILABLE_RETRY = timedelta(hours=6)
MAX_ATTEMPTS = 3
MAX_PER_SCAN = 4  # meetings read per call (each is a transcript download and, on Bedrock, model calls)
SLACK_BEFORE = timedelta(minutes=30)
SLACK_AFTER = timedelta(hours=3)
MAX_TURNS = 2000
MIN_INTERVAL_S = 60.0


def extractor_for(state: AppState) -> Any:
    if state.settings.drafter == "bedrock":
        from vanimo.memory.model import BedrockAtomExtractor

        return BedrockAtomExtractor(state.llm, state.router)
    return OfflineAtomExtractor()


@dataclass
class IngestResult:
    stored: int = 0  # meetings remembered in this call
    atoms: int = 0
    promises: int = 0
    excluded: int = 0
    waiting: int = 0  # ended meetings with no transcript yet
    pending: bool = False  # more meetings to read than one call reads
    skipped: bool = False  # throttled
    off: bool = False  # the organisation turned meeting memory off
    unavailable: str | None = None  # content-free reason transcripts can't be read (disabled, permission)
    counts: dict[str, int] = field(default_factory=dict)

    def add(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n


class Throttle:
    def __init__(self) -> None:
        self._last: dict[str, float] = {}

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        if now - self._last.get(key, -1e9) < MIN_INTERVAL_S:
            return False
        if len(self._last) > 10_000:
            self._last.clear()
        self._last[key] = now
        return True


THROTTLE = Throttle()


async def meeting_memory_on(conn: AsyncConnection) -> bool:
    on = (await conn.execute(text("select meeting_memory from vanimo.tenant_policies"))).scalar_one_or_none()
    return on is not False


def _due_again(prior: Any, event: Event, now: datetime) -> bool:
    """Whether an occurrence seen before should be looked at again."""
    if prior.state in ("stored", "deleted", "empty"):
        return False
    if prior.state == "no_transcript":
        return event.end > now - NO_TRANSCRIPT_RETRY_FOR and prior.checked_at < now - RECHECK_EVERY
    if prior.state == "unavailable":
        return prior.checked_at < now - UNAVAILABLE_RETRY
    return prior.attempts < MAX_ATTEMPTS  # failed


def _internal(domain: str, org_domains: frozenset[str]) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in org_domains)


# --- speakers ----------------------------------------------------------------------------------
_PAREN = re.compile(r"\s*[(\[][^)\]]*[)\]]")


def _fold(name: str) -> str:
    name = _PAREN.sub(" ", name)  # "John Miller (Guest)", "(External)", "[Contractor]"
    if name.count(",") == 1:
        last, first = (x.strip() for x in name.split(","))
        name = f"{first} {last}"
    return " ".join(unicodedata.normalize("NFKC", name).casefold().split())


@dataclass
class Roster:
    """Who may speak in an occurrence: its invitees and the user, by name (Teams attributes speech to
    display names). An ambiguous name (two invitees share it) matches nobody."""

    me: Address
    by_name: dict[str, Address | None] = field(default_factory=dict)

    def add(self, a: Address, name: str | None = None) -> None:
        key = _fold(name or a.name or "")
        if not key:
            return
        known = self.by_name.get(key, a)
        self.by_name[key] = a if known is not None and known.email.lower() == a.email.lower() else None

    def find(self, speaker: str) -> Address | None:
        return self.by_name.get(_fold(speaker))


@dataclass
class Built:
    turns: list[Turn]
    tokens: dict[str, tuple[str, str]]
    people: dict[str, Address]  # everyone but the user who was invited or spoke
    title: str
    attributed: bool
    started_at: datetime
    excluded: bool = False
    roster: dict[str, str] = field(default_factory=dict)  # person token -> side, everyone in the meeting


def _speaker_token(redactor: Redactor, a: Address, *, me: bool) -> tuple[str, str]:
    name = a.name or a.email.split("@")[0]
    return redactor.person_base(Person(name, a.email.lower()), me=me) + ".full⟧", name


def build(
    event: Event,
    transcripts: list[Transcript],
    *,
    roster: Roster,
    known: dict[str, list[Address]],
    directory: Directory,
    redactor_for: Any,
    ex_engine: Any,
    org_domains: frozenset[str],
    result: IngestResult,
) -> Built:
    """L0 transcripts → L1 turns with speakers, in memory. `known`: the user's Sources index by
    folded name, for people who spoke without being invited. A name two known people share (a
    look-alike address, a namesake) matches nobody; if either is excluded, so is the meeting."""
    me = roster.me.email.lower()
    first = min(t.ref.created_at for t in transcripts)
    attributed = all(t.attributed for t in transcripts)
    people = {a.email.lower(): a for a in roster.by_name.values() if a and a.email.lower() != me}
    raw: list[tuple[int, int, Address | None, str]] = []
    unknown: dict[str, str] = {}  # names of people whose words are left out, still redacted where mentioned
    for tr in sorted(transcripts, key=lambda t: t.ref.created_at):
        shift = int((tr.ref.created_at - first).total_seconds() * 1000)
        for cue in vtt.turns(list(tr.cues)):
            who: Address | None = None
            if attributed and cue.speaker:
                who = roster.find(cue.speaker)
                if who is None and (namesakes := known.get(_fold(cue.speaker))):
                    # Not invited, but someone you know: your rules about them apply to this meeting.
                    if any(ex_engine.person_reasons(k) for k in namesakes):
                        return Built([], {}, {}, "", attributed, first, excluded=True)
                    who = namesakes[0] if len(namesakes) == 1 else None
                if who is None:
                    result.add("unknown_speaker")
                    name = " ".join(_PAREN.sub(" ", cue.speaker).split())
                    if name:
                        unknown.setdefault(_fold(name), name)
                    continue
                if who.email.lower() != me:
                    people.setdefault(who.email.lower(), who)
            elif attributed:
                result.add("unknown_speaker")
                continue
            raw.append((cue.start_ms + shift, cue.end_ms + shift, who, cue.text))
    # People nobody could identify have no address: their names join the gazetteer without one, so
    # "thanks, Jordan" becomes a token like any known name (never a person you can be matched to).
    redactor: Redactor = redactor_for([*people.values(), *(Address("", n) for n in unknown.values())])
    tokens: dict[str, tuple[str, str]] = {}
    sides: dict[str, str] = {}
    for a in [roster.me, *people.values()]:
        is_me = a.email.lower() == me
        tok, value = _speaker_token(redactor, a, me=is_me)
        tokens.setdefault(tok, ("person", value))
        sides[tok] = "me" if is_me else ("internal" if _internal(a.domain, org_domains) else "external")
    turns: list[Turn] = []
    for start, end, who, words in raw[:MAX_TURNS]:
        try:
            red = redactor.redact(words)
        except RedactionBlocked as e:
            result.add(f"blocked_{e.reason}")
            continue
        if not red.text.strip():
            continue
        speaker, side = None, "unknown"
        if who is not None:
            is_me = who.email.lower() == me
            speaker, value = _speaker_token(redactor, who, me=is_me)
            tokens.setdefault(speaker, ("person", value))
            side = "me" if is_me else ("internal" if _internal(who.domain, org_domains) else "external")
        tokens |= red.tokens
        turns.append(Turn(len(turns), start, end, speaker, side, red.text))  # type: ignore[arg-type]
    try:
        title_red = redactor.redact(event.subject or "")
        title, tokens = title_red.text or "(no subject)", tokens | title_red.tokens
    except RedactionBlocked:
        title = "(meeting)"
    return Built(turns, tokens, people, title, attributed, first, roster=sides)


def occurrence_transcripts(event: Event, refs: list[TranscriptRef], series: list[Event]) -> list[TranscriptRef]:
    """A series' occurrences share one online meeting and its transcript list: an occurrence takes the
    transcripts that started in its own time (from 30 minutes before it to 3 hours after it ended, and
    before the next occurrence)."""
    later = [e.start for e in series if e.start > event.start]
    stop = min([event.end + SLACK_AFTER, *[s - SLACK_BEFORE for s in later]])
    return [r for r in refs if event.start - SLACK_BEFORE <= r.created_at <= stop]


# --- storing -----------------------------------------------------------------------------------
async def _record(
    conn: AsyncConnection, user: UserRef, kind: str, mh: str, state: str, detail: str, ends: datetime
) -> None:
    await conn.execute(
        text(
            "insert into vanimo.meeting_ingests (owner_user_id, tenant_id, source_kind, meeting_hash, state, detail, "
            "ends_at) values (:u, :t, :k, :m, :s, :d, :e) on conflict (owner_user_id, source_kind, meeting_hash) "
            "do update set state = excluded.state, detail = excluded.detail, checked_at = now(), "
            "attempts = case when excluded.state = 'failed' then vanimo.meeting_ingests.attempts + 1 else 1 end"
        ),
        {"u": user.user_id, "t": user.tenant_id, "k": kind, "m": mh, "s": state, "d": detail[:40], "e": ends},
    )


async def record(state: AppState, user: UserRef, kind: str, mh: str, st: str, detail: str, ends: datetime) -> None:
    async with user_tx(state.engine, user) as conn:
        if st == "deleted" or not await _tombstoned(conn, kind, mh):
            await _record(conn, user, kind, mh, st, detail, ends)


async def _tombstoned(conn: AsyncConnection, kind: str, mh: str) -> bool:
    row = (
        await conn.execute(
            text("select state from vanimo.meeting_ingests where source_kind = :k and meeting_hash = :m"),
            {"k": kind, "m": mh},
        )
    ).scalar_one_or_none()
    return row == "deleted"


def _tokens_in(*texts: str | None) -> set[str]:
    out: set[str] = set()
    for t in texts:
        out |= set(TOKEN.findall(t or ""))
    return out


async def save(
    state: AppState,
    user: UserRef,
    source_kind: str,
    event: Event,
    built: Built,
    atoms: list[Any],
    version: int,
    *,
    extractor: str,
    hasher: Any,
    ex_engine: Any,
    directory: Directory,
    org_domains: frozenset[str],
) -> tuple[int, int] | None:
    """Stores one episode, its L1 turns, atoms and the user's own promises. None if the controls
    changed since the scan began (a rule or never-send word added meanwhile wins)."""
    v, t, u = state.vault, user.tenant_id, user.user_id
    now = datetime.now(UTC)
    mh = hasher("meeting", event.id)
    sh = hasher("series", event.series_id) if event.series_id else None
    me = directory.me.email.lower() if directory.me.email else ""
    people = [(hasher("person", e), ex_engine.domain_hashes(a.domain)) for e, a in sorted(built.people.items())]
    roster = sorted(built.roster)
    async with user_tx(state.engine, user) as conn:
        await lock_user_controls(conn, user)
        if await controls_version(conn) != version:
            return None
        if await _tombstoned(conn, source_kind, mh):
            return 0, 0
        matcher = await load_matcher(conn, v, user)

        def m(value: str | None) -> str | None:
            return matcher.mask(value, opaque=L1_MARKS)[0] if value else value

        row = (
            await conn.execute(
                text(
                    "insert into vanimo.episodes (tenant_id, owner_user_id, source_kind, meeting_hash, series_hash, "
                    "title_enc, starts_at, ends_at, transcript_at, people, roster, external, organizer_is_me, "
                    "attribution, extractor, segments_until, counts) values (:t, :u, :k, :mh, :sh, :title, :s, :e, "
                    ":tr, "
                    "cast(:people as jsonb), cast(:roster as jsonb), :ext, :org, :attr, :ex, :until, "
                    "cast(:counts as jsonb)) on conflict (owner_user_id, meeting_hash) do nothing returning id"
                ),
                {
                    "t": t,
                    "u": u,
                    "k": source_kind,
                    "mh": mh,
                    "sh": sh,
                    "title": v.encrypt_user(t, u, m(built.title), "episode_title"),
                    "s": event.start,
                    "e": event.end,
                    "tr": built.started_at,
                    "people": json.dumps([{"p": p, "d": d} for p, d in people]),
                    "roster": json.dumps([{"t": s, "s": built.roster[s]} for s in roster]),
                    "ext": any(not _internal(a.domain, org_domains) for a in built.people.values()),
                    "org": event.is_organizer or bool(event.organizer and event.organizer.email.lower() == me),
                    "attr": "named" if built.attributed else "unattributed",
                    "ex": extractor,
                    "until": now + timedelta(days=state.settings.transcript_retention_days),
                    "counts": json.dumps({"turns": len(built.turns)}),
                },
            )
        ).first()
        if row is None:
            return 0, 0  # stored meanwhile by another scan
        episode = row.id
        expires = now + timedelta(days=state.settings.transcript_retention_days)
        if built.turns:
            await conn.execute(
                text(
                    "insert into vanimo.episode_segments (tenant_id, owner_user_id, episode_id, ordinal, starts_ms, "
                    "ends_ms, speaker, speaker_side, text_enc, expires_at) values (:t, :u, :ep, :n, :s, :e, :sp, "
                    ":side, :x, :exp)"
                ),
                [
                    {
                        "t": t,
                        "u": u,
                        "ep": episode,
                        "n": x.ordinal,
                        "s": x.start_ms,
                        "e": x.end_ms,
                        "sp": x.speaker,
                        "side": x.side,
                        "x": v.encrypt_user(t, u, m(x.text), "segment_text"),
                        "exp": expires,
                    }
                    for x in built.turns
                ],
            )
        by_turn = {x.ordinal: x for x in built.turns}
        stored_atoms = 0
        used: set[str] = set(roster) | _tokens_in(built.title)
        for a in atoms:
            turn = by_turn[a.turn]
            said = built.started_at + timedelta(milliseconds=max(turn.start_ms, 0))
            r = await conn.execute(
                text(
                    "insert into vanimo.memory_atoms (tenant_id, owner_user_id, episode_id, kind, atom_hash, text_enc, "
                    "quote_enc, speaker, speaker_side, owner, said_at, seg_from, seg_to, starts_ms, ends_ms, due_at, "
                    "due_phrase_enc, confidence, trust, extractor, expires_at) values (:t, :u, :ep, :kind, :h, :x, "
                    ":q, :sp, :side, :own, :said, :n, :n, :s, :e, :due, :phrase, :c, :trust, :ex, :exp) "
                    "on conflict (owner_user_id, atom_hash) do nothing returning id"
                ),
                {
                    "t": t,
                    "u": u,
                    "ep": episode,
                    "kind": a.kind,
                    "h": v.key_hash(t, "atom", f"{mh}:{a.kind}:{ledger._norm(a.quote)}"),
                    "x": v.encrypt_user(t, u, m(a.text), "atom_text"),
                    "q": v.encrypt_user(t, u, m(a.quote), "atom_quote"),
                    "sp": turn.speaker,
                    "side": turn.side,
                    "own": a.owner
                    if a.owner and re.fullmatch(r"⟦(ME|PERSON_[0-9a-f]{8})(\.full|\.last)?⟧", a.owner)
                    else None,
                    "said": said,
                    "n": a.turn,
                    "s": turn.start_ms,
                    "e": turn.end_ms,
                    "due": a.due_at,
                    "phrase": v.encrypt_user(t, u, m(a.due_phrase), "atom_due"),
                    "c": a.confidence,
                    "trust": "high" if built.attributed else "medium",
                    "ex": extractor,
                    "exp": said + timedelta(days=state.settings.memory_retention_days),
                },
            )
            if r.first():
                stored_atoms += 1
                used |= _tokens_in(a.text, a.quote)
                if a.owner:  # any stored form of the owner's name, for display
                    stem = a.owner.split(".")[0].removesuffix("⟧")
                    used |= {k for k in built.tokens if k.split(".")[0].removesuffix("⟧") == stem}
        for x in built.turns:
            used |= _tokens_in(x.text)
        mine = my_promises(event, built, atoms, hasher, people, directory, org_domains, mh, sh)
        promises = await ledger.insert(conn, v, user, source_kind, mine, matcher, extractor=extractor)
        await ledger.save_tokens(conn, v, user, {k: val for k, val in built.tokens.items() if k in used}, matcher)
        await _record(
            conn, user, source_kind, mh, "stored", "attributed" if built.attributed else "unattributed", event.end
        )
    return stored_atoms, promises


def meeting_item(hasher: Any, meeting_hash: str) -> str:
    """The ledger's item key for a meeting's promises (from the occurrence's hash: its ID isn't stored)."""
    return hasher("item", f"meeting-episode:{meeting_hash}")


def my_promises(
    event: Event,
    built: Built,
    atoms: list[Any],
    hasher: Any,
    people: list[tuple[str, list[str]]],
    directory: Directory,
    org_domains: frozenset[str],
    mh: str,
    sh: str | None,
) -> list[ledger.Candidate]:
    """The user's own promises in the meeting, for the commitments ledger (channel "meeting"; no
    conversation to follow up in, so no follow-up draft). Needs speaker attribution."""
    by_turn = {x.ordinal: x for x in built.turns}
    mine = [a for a in atoms if a.kind == "commitment" and by_turn[a.turn].side == "me"]
    if not mine:
        return []
    unit = ledger.Unit(
        channel="meeting",
        item_hash=meeting_item(hasher, mh),
        thread_hash=mh,
        people=people,
        relationship=labels.relationship(
            list(built.people.values()), manager=directory.manager, reports=directory.reports, org_domains=org_domains
        ),
        sent_at=built.started_at,
        text="",
        tokens=built.tokens,
        ref=None,
        meeting_hash=mh,
        series_hash=sh,
    )
    out = []
    for n, a in enumerate(mine):
        said = built.started_at + timedelta(milliseconds=max(by_turn[a.turn].start_ms, 0))
        u = ledger.Unit(**{**unit.__dict__, "sent_at": said})
        out.append(ledger.Candidate(u, n, Found(a.quote, a.text, a.due_phrase, a.due_at)))
    return out


# --- the scan ----------------------------------------------------------------------------------
async def scan(state: AppState, user: UserRef, source: WorkspaceSource, *, self_email: str) -> IngestResult:
    from vanimo.drafting.service import _known

    out = IngestResult()
    await require_review_done(state.engine, user, source.kind)
    async with user_tx(state.engine, user) as conn:
        if not await meeting_memory_on(conn):
            out.off = True
            return out
    if not THROTTLE.allow(f"{user.user_id}:{source.kind}"):
        out.skipped = True
        return out
    now = datetime.now(UTC)
    me = self_email.lower()
    hasher = hasher_for(state.vault, user)
    sample = await source.org_domains() if source.kind == "sample" else frozenset()
    async with user_tx(state.engine, user) as conn:
        version = await controls_version(conn)
        ex_engine = await load_engine(conn, state.vault, user, self_email=me, extra_org_domains=sample)
        matcher = await load_matcher(conn, state.vault, user)
        _, known_people = await _known(conn, state, user)
        priors = {
            r.meeting_hash: r
            for r in (
                await conn.execute(
                    text(
                        "select meeting_hash, state, attempts, checked_at from vanimo.meeting_ingests "
                        "where source_kind = :k"
                    ),
                    {"k": source.kind},
                )
            ).all()
        }
    directory = await state.directory_cache.get((str(user.user_id), source.kind), source, me)
    org_domains = directory.org_domains | sample

    # 1-2. Calendar metadata first: which ended Teams meetings may be read at all.
    events = [e async for e in source.events(now - LOOKBACK, now)]
    todo: list[Event] = []
    for e in events:
        if not e.is_online or not e.join_url or e.end > now - SETTLE:
            continue
        prior = priors.get(hasher("meeting", e.id))
        if prior is not None and not _due_again(prior, e, now):
            continue
        if e.is_private:
            out.add("private")
            continue
        if e.organizer is None or not _internal(e.organizer.domain, org_domains):
            out.add("other_organisation")  # its transcript lives in the organiser's tenant
            continue
        if ex_engine.meeting(e).excluded:
            out.excluded += 1
            continue
        todo.append(e)
    todo.sort(key=lambda e: e.start, reverse=True)  # the most recent meetings first
    out.pending = len(todo) > MAX_PER_SCAN
    known: dict[str, list[Address]] = {}
    for p in known_people:
        if p.email:
            same = known.setdefault(_fold(p.full_name), [])
            if all(a.email.lower() != p.email.lower() for a in same):
                same.append(Address(p.email.lower(), p.full_name))
    extractor = extractor_for(state)
    listed: dict[str, list[TranscriptRef]] = {}
    for e in todo[:MAX_PER_SCAN]:
        mh = hasher("meeting", e.id)
        try:
            # 3. The transcript list (metadata), once per online meeting (a series shares one).
            if e.join_url not in listed:
                listed[e.join_url or ""] = await source.meeting_transcripts(e)
            series = [x for x in events if e.series_id and x.series_id == e.series_id]
            refs = occurrence_transcripts(e, listed[e.join_url or ""], series)
            if not refs:
                out.waiting += 1
                await record(state, user, source.kind, mh, "no_transcript", "", e.end)
                continue
            transcripts = [await source.transcript(r) for r in sorted(refs, key=lambda r: r.created_at)]
        except TranscriptsUnavailable as exc:
            # Too large, expired or gone won't change: recorded as done, never downloaded again.
            terminal = exc.reason in ("too_large", "expired", "not_found")
            await record(state, user, source.kind, mh, "empty" if terminal else "unavailable", exc.reason, e.end)
            if exc.reason in ("disabled", "permission"):
                out.unavailable = exc.reason  # the same for every meeting: stop asking
                break
            continue
        except Exception as exc:
            log.warning("memory.read_failed", error_type=type(exc).__name__)
            await record(state, user, source.kind, mh, "failed", "read_failed", e.end)
            continue

        # 4. Speakers and L1, in memory.
        roster = Roster(Address(me, directory.me.full_name))
        roster.add(roster.me, directory.me.full_name)
        for a in (*e.attendees, *([e.organizer] if e.organizer else [])):
            roster.add(a)

        def redactor_for(people: list[Address], invited: tuple[Address, ...] = e.attendees) -> Redactor:
            return build_redactor(matcher, hasher, directory, [*invited, *people], known_people)

        built = build(
            e, transcripts, roster=roster, known=known, directory=directory, redactor_for=redactor_for,
            ex_engine=ex_engine, org_domains=org_domains, result=out,
        )  # fmt: skip
        if built.excluded:
            out.excluded += 1
            await record(state, user, source.kind, mh, "empty", "excluded_speaker", e.end)
            continue
        if not built.turns:
            await record(state, user, source.kind, mh, "empty", "no_turns", e.end)
            continue

        # 5. Atoms in L1, stored with the user's own promises.
        try:
            atoms = await extractor.find(built.turns, started_at=built.started_at, tz=state.settings.cell_config.zone)
        except Exception as exc:
            log.warning("memory.extract_failed", error_type=type(exc).__name__)
            await record(state, user, source.kind, mh, "failed", "extract_failed", e.end)
            continue
        saved = await save(
            state, user, source.kind, e, built, atoms, version, extractor=extractor.kind, hasher=hasher,
            ex_engine=ex_engine, directory=directory, org_domains=org_domains,
        )  # fmt: skip
        if saved is None:
            out.add("controls_changed")
            break
        out.stored += 1
        out.atoms += saved[0]
        out.promises += saved[1]
    log.info("memory.scanned", count=out.stored, outcome=out.unavailable or "ok")
    return out


def summary(r: IngestResult) -> dict[str, Any]:
    return {
        "stored": r.stored,
        "atoms": r.atoms,
        "promises": r.promises,
        "excluded": r.excluded,
        "waiting": r.waiting,
        "pending": r.pending,
        "skipped": r.skipped,
        "off": r.off,
        "unavailable": r.unavailable,
        "leftOut": r.counts.get("unknown_speaker", 0) + sum(v for k, v in r.counts.items() if k.startswith("blocked_")),
    }
