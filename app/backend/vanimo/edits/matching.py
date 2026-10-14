"""Draft ↔ sent matching (architecture §9.2: "the only reliable signal", research R05 §7.7).

For every stored draft still pending, look at the user's recent **sent** mail:
  * a reply draft matches the first message the user sent in the same conversation after it;
  * a new-email draft matches a sent message to any of the same people that shares enough text;
  * within 72 hours, otherwise the draft is marked unmatched (discarded).
Headers first: the exclusion engine decides on the sent message before its text is read
(two-phase, §6.5 X2); an excluded one ends the draft's tracking. The sent text is redacted to L1
in memory, compared with the draft's L1, and only the outcome, the edit kinds and the rules'
evidence are stored — never the sent text.

The sample workspace has no new sent mail, so its "Mark as sent" action feeds the user's edited
text through the same path (`record_sent`).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from vanimo.controls.neversend import Matcher, Term
from vanimo.controls.store import hasher_for, load_engine, load_terms, lock_user_controls
from vanimo.db.session import UserRef, user_tx
from vanimo.drafting.context import DraftError, build_redactor
from vanimo.edits import rules
from vanimo.edits.diff import REWRITE_SIMILARITY, Comparison, compare, similarity
from vanimo.logs import get_logger
from vanimo.redaction.parse import strip_quotes, strip_signature_noise
from vanimo.redaction.pipeline import Person, RedactionBlocked
from vanimo.sources.base import Address, SentHeader, WorkspaceSource
from vanimo.state import AppState

log = get_logger("vanimo.edits")

MATCH_WINDOW = timedelta(hours=72)
RECENT_SENT = 50
MAX_FETCHES = 10  # sent bodies read per sync (denial of wallet, Graph throttling)


async def _context(state: AppState, user: UserRef, source: WorkspaceSource, self_email: str) -> dict[str, Any]:
    from vanimo.drafting.service import _known, _sample_domains

    async with user_tx(state.engine, user) as conn:
        engine = await load_engine(
            conn, state.vault, user, self_email=self_email, extra_org_domains=_sample_domains(source)
        )
        terms = await load_terms(conn, state.vault, user)
        _, known_people = await _known(conn, state, user)
    directory = await state.directory_cache.get((str(user.user_id), source.kind), source, self_email)
    matcher = Matcher([Term(t["term_id"], t["text"], t["kind"], tuple(t["variants"]), t["folds"]) for t in terms])
    return {
        "engine": engine,
        "matcher": matcher,
        "known_people": known_people,
        "directory": directory,
        "hasher": hasher_for(state.vault, user),
    }


def _to_l1(ctx: dict[str, Any], body: str, people: list[Address]) -> str | None:
    redactor = build_redactor(ctx["matcher"], ctx["hasher"], ctx["directory"], people, ctx["known_people"])
    try:
        return redactor.redact(strip_signature_noise(strip_quotes(body)[0])[:8000]).text
    except RedactionBlocked:
        return None


async def _store_match(
    state: AppState, user: UserRef, draft: Any, comparison: Comparison, source_kind: str
) -> dict[str, Any]:
    """Record the outcome and observations under the controls lock; the draft must still exist
    (a purge may have deleted it meanwhile, and then nothing is recorded)."""
    hasher = hasher_for(state.vault, user)
    async with user_tx(state.engine, user) as conn:
        await lock_user_controls(conn, user)
        alive = (
            await conn.execute(
                text("select id from vanimo.drafts where id = :id and match_state = 'pending' for update"),
                {"id": draft.id},
            )
        ).first()
        if alive is None:
            return {"recorded": False}
        await rules.record(
            conn,
            state.vault,
            user,
            hasher,
            draft_id=str(draft.id),
            source_kind=source_kind,
            relationship=draft.relationship,
            comparison=comparison,
        )
        await conn.execute(
            text(
                "update vanimo.drafts set match_state = 'matched', "
                "placed_state = case when placed_state = 'placed' then 'sent' else placed_state end where id = :id"
            ),
            {"id": draft.id},
        )
    return {"recorded": True}


async def _pending(state: AppState, user: UserRef, source_kind: str) -> list[Any]:
    async with user_tx(state.engine, user) as conn:
        return list(
            (
                await conn.execute(
                    text(
                        "select id, mode, thread_hash, people, text_enc, created_at, relationship from vanimo.drafts "
                        "where match_state = 'pending' and source_kind = :k order by created_at"
                    ),
                    {"k": source_kind},
                )
            ).all()
        )


async def sync(state: AppState, user: UserRef, source: WorkspaceSource, *, self_email: str) -> dict[str, int]:
    """Match pending drafts to recent sent mail. Returns content-free counts."""
    counts = {"matched": 0, "unmatched": 0, "excluded": 0, "pending": 0}
    pending = await _pending(state, user, source.kind)
    if not pending:
        return counts
    ctx = await _context(state, user, source, self_email)
    hasher = ctx["hasher"]
    now = datetime.now(UTC)
    sent: list[SentHeader] = sorted(await source.recent_sent(RECENT_SENT), key=lambda h: h.sent_at)
    fetches = 0
    for d in pending:
        window_end = d.created_at + MATCH_WINDOW
        draft_people = {p["p"] for p in d.people}
        candidates = [
            h
            for h in sent
            if d.created_at <= h.sent_at <= window_end
            and (
                (d.mode == "reply" and d.thread_hash and hasher("thread", h.conversation_id) == d.thread_hash)
                or (d.mode == "new" and draft_people & {hasher("person", a.email.lower()) for a in h.recipients})
            )
        ]
        state_now = "pending"
        draft_l1 = state.vault.decrypt_user(user.tenant_id, user.user_id, d.text_enc, "draft_text") or ""
        for h in candidates[:3]:
            if ctx["engine"].message(h).excluded:
                state_now = "excluded"  # the conversation is excluded now: stop tracking, read nothing
                break
            if fetches >= MAX_FETCHES:
                break
            fetches += 1
            m = await source.message(h.id)
            if m is None:
                continue
            sent_l1 = _to_l1(ctx, m.body, list(h.participants))
            if sent_l1 is None:
                continue
            if d.mode == "new" and similarity(draft_l1, sent_l1) < REWRITE_SIMILARITY:
                continue  # a different email to the same person
            result = await _store_match(state, user, d, compare(draft_l1, sent_l1), source.kind)
            state_now = "matched" if result["recorded"] else "gone"
            break
        if state_now == "pending" and now > window_end:
            state_now = "unmatched"
        if state_now in ("unmatched", "excluded"):
            async with user_tx(state.engine, user) as conn:
                await conn.execute(
                    text("update vanimo.drafts set match_state = :s where id = :id and match_state = 'pending'"),
                    {"s": state_now, "id": d.id},
                )
        if state_now in counts:
            counts[state_now] += 1
    log.info("edits.sync", count=counts["matched"], outcome=f"unmatched_{counts['unmatched']}")
    return counts


async def record_sent(
    state: AppState, user: UserRef, source: WorkspaceSource, *, self_email: str, draft_id: str, sent_text: str
) -> Comparison:
    """Sample workspace only: the user's final text stands in for the message they sent."""
    if source.kind != "sample":
        raise DraftError("sample_workspace_only", 404)
    async with user_tx(state.engine, user) as conn:
        d = (
            await conn.execute(
                text(
                    "select id, mode, thread_hash, people, text_enc, created_at, relationship, match_state "
                    "from vanimo.drafts where id = :id and source_kind = 'sample'"
                ),
                {"id": draft_id},
            )
        ).first()
    if d is None:
        raise DraftError("not_found", 404)
    if d.match_state != "pending":
        raise DraftError("already_matched", 409)
    ctx = await _context(state, user, source, self_email)
    people = [Address(p.email or "", p.full_name) for p in ctx["known_people"] if isinstance(p, Person) and p.email]
    sent_l1 = _to_l1(ctx, sent_text, people)
    if sent_l1 is None:
        raise DraftError("text_blocked", 422)
    draft_l1 = state.vault.decrypt_user(user.tenant_id, user.user_id, d.text_enc, "draft_text") or ""
    comparison = compare(draft_l1, sent_l1)
    result = await _store_match(state, user, d, comparison, "sample")
    if not result["recorded"]:
        raise DraftError("already_matched", 409)
    return comparison
