"""The drafts queue and drafts in the Outlook Drafts folder (MVP plan M4; architecture §3.2-§3.3).

**Waiting for your reply** — recent conversations whose latest message is from someone else and
that you haven't answered since (headers only: your inbox and Sent Items), minus ones you
dismissed. Each is triaged:
  * metadata first: automated senders (no-reply, notifications) and mail you're only copied on
    rank low; an excluded conversation is listed as excluded and its text is never read;
  * then, only after your review and for at most a dozen allowed conversations, the latest
    message's own words are read in memory to see whether it asks something (question,
    request, scheduling). Nothing is stored.

**Drafts in your Drafts folder** (opt-in per user, allowed by the organisation): a reply draft is
created in the conversation with Graph `createReply`, so it shows in every Outlook client,
including mobile. A draft with a blocking check (payment change, look-alike domain) is never
put there. Vanimo never sends.

**Tidying**: placed drafts older than your setting (3 days by default) are deleted only if they
are still unsent and untouched since Vanimo wrote them; if you replied in the conversation
yourself, the unused draft is removed. Anything you edited or sent stays.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from vanimo import audit
from vanimo.controls.store import hasher_for, load_engine
from vanimo.db.session import UserRef, user_tx
from vanimo.drafting.context import DraftError
from vanimo.gates import onboarding_state
from vanimo.learning import labels
from vanimo.logs import get_logger
from vanimo.redaction.parse import strip_quotes
from vanimo.sources.base import Address, WorkspaceSource
from vanimo.state import AppState

log = get_logger("vanimo.queue")

WAITING_DAYS = 14
MAX_TRIAGE_READS = 12
EDIT_GRACE = timedelta(minutes=2)  # a draft modified later than this after placing was edited by the user
AUTOMATED = re.compile(
    r"^(no-?reply|do-?not-?reply|notifications?|notify|mailer-daemon|postmaster|alerts?|bounces?|"
    r"newsletters?|updates|digest|calendar-notification)([.+_-][^@]*)?@",
    re.I,
)
NEEDS_REPLY_INTENTS = {
    "question": "asks a question",
    "request": "asks you to do something",
    "scheduling": "about a meeting time",
}


@dataclass
class Settings:
    outlook_drafts: bool
    stale_days: int
    allowed_by_organisation: bool


async def load_settings(conn: Any) -> Settings:
    row = (await conn.execute(text("select outlook_drafts, stale_days from vanimo.drafting_settings"))).first()
    allowed = (await conn.execute(text("select server_drafts from vanimo.tenant_policies"))).scalar_one_or_none()
    return Settings(
        outlook_drafts=bool(row.outlook_drafts) if row else False,
        stale_days=row.stale_days if row else 3,
        allowed_by_organisation=True if allowed is None else bool(allowed),
    )


async def save_settings(state: AppState, user: UserRef, *, outlook_drafts: bool, stale_days: int) -> Settings:
    async with user_tx(state.engine, user) as conn:
        await conn.execute(
            text(
                "insert into vanimo.drafting_settings (owner_user_id, tenant_id, outlook_drafts, stale_days) "
                "values (:u, :t, :o, :d) on conflict (owner_user_id) do update set outlook_drafts = :o, "
                "stale_days = :d, updated_at = now()"
            ),
            {"u": user.user_id, "t": user.tenant_id, "o": outlook_drafts, "d": stale_days},
        )
        return await load_settings(conn)


# --- waiting for your reply ---------------------------------------------------------------------
@dataclass
class QueueItem:
    conversation_id: str
    subject: str | None
    sender: Address
    received_at: datetime
    needs_reply: bool
    reason: str  # plain words, content-free
    excluded: bool
    excluded_by: str | None
    cc_only: bool
    draft: dict[str, Any] | None  # the latest Vanimo draft in this conversation, metadata only


async def waiting(state: AppState, user: UserRef, source: WorkspaceSource, *, self_email: str) -> list[QueueItem]:
    from vanimo.controls.neversend import render_removed
    from vanimo.controls.store import load_matcher
    from vanimo.drafting.context import refusal
    from vanimo.drafting.service import _sample_domains

    me = self_email.lower()
    hasher = hasher_for(state.vault, user)
    async with user_tx(state.engine, user) as conn:
        onboarding, _ = await onboarding_state(conn, source.kind)
        engine = await load_engine(conn, state.vault, user, self_email=me, extra_org_domains=_sample_domains(source))
        matcher = await load_matcher(conn, state.vault, user)
        dismissed = set((await conn.execute(text("select thread_hash from vanimo.queue_dismissals"))).scalars().all())
        drafts: dict[str, Any] = {}
        for r in (
            await conn.execute(
                text(
                    "select id, thread_hash, created_at, placed_state, placed_link_enc, outcome, match_state, checks "
                    "from vanimo.drafts where source_kind = :k and thread_hash is not null order by created_at"
                ),
                {"k": source.kind},
            )
        ).all():
            drafts[r.thread_hash] = r  # the latest per conversation wins
    received = await source.recent_received(25)
    last_sent: dict[str, datetime] = {}
    for h in await source.recent_sent(50):
        last_sent[h.conversation_id] = max(h.sent_at, last_sent.get(h.conversation_id, h.sent_at))
    cutoff = datetime.now(UTC) - timedelta(days=WAITING_DAYS)
    items: list[QueueItem] = []
    reads = 0
    for h in received:
        if h.received_at < cutoff or last_sent.get(h.conversation_id, h.received_at) > h.received_at:
            continue  # old, or you've replied since
        th = hasher("thread", h.conversation_id)
        if th in dismissed:
            continue
        decision = engine.conversation(h.conversation_id, [h.sender, *h.to, *h.cc])
        cc_only = not any(a.email.lower() == me for a in h.to)
        automated = bool(AUTOMATED.match(h.sender.email))
        needs, reason = (False, "automated sender") if automated else (not cc_only, "you're copied" if cc_only else "")
        if decision.excluded:
            needs, reason = False, "excluded"
        elif not automated and onboarding == "review_done" and reads < MAX_TRIAGE_READS:
            reads += 1
            m = await source.message(h.id)
            intent = labels.intent(strip_quotes(m.body)[0]) if m else "general"
            if intent in NEEDS_REPLY_INTENTS:
                needs, reason = True, NEEDS_REPLY_INTENTS[intent]
            elif not cc_only:
                needs, reason = False, "no question or request found"
        d = drafts.get(th)
        items.append(
            QueueItem(
                conversation_id=h.conversation_id,
                subject=render_removed(matcher.mask(h.subject)[0]) if h.subject else None,
                sender=h.sender,
                received_at=h.received_at,
                needs_reply=needs,
                reason=reason,
                excluded=decision.excluded,
                excluded_by=refusal(decision).extra["by"] if decision.excluded else None,  # type: ignore[dict-item]
                cc_only=cc_only,
                draft=_draft_meta(state, user, d) if d else None,
            )
        )
    items.sort(key=lambda i: (not i.needs_reply, i.excluded, -i.received_at.timestamp()))
    return items


def _draft_meta(state: AppState, user: UserRef, d: Any) -> dict[str, Any]:
    return {
        "id": str(d.id),
        "createdAt": d.created_at,
        "placed": d.placed_state == "placed",
        "placedState": d.placed_state,
        "webLink": state.vault.decrypt_user(user.tenant_id, user.user_id, d.placed_link_enc, "draft_link"),
        "outcome": d.outcome,
        "matchState": d.match_state,
        "blocked": any(c.get("severity") == "block" for c in d.checks),
    }


async def dismiss(state: AppState, user: UserRef, conversation_id: str) -> None:
    async with user_tx(state.engine, user) as conn:
        await conn.execute(
            text(
                "insert into vanimo.queue_dismissals (tenant_id, owner_user_id, thread_hash) values (:t, :u, :h) "
                "on conflict do nothing"
            ),
            {"t": user.tenant_id, "u": user.user_id, "h": hasher_for(state.vault, user)("thread", conversation_id)},
        )


# --- drafts in the Outlook Drafts folder --------------------------------------------------------
async def place(
    state: AppState,
    user: UserRef,
    source: WorkspaceSource,
    *,
    draft_id: str,
    text_shown: str,
    confirmed: bool = False,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Put a reply draft in the user's Drafts folder. `text_shown` is the text on the user's screen
    (possibly edited by them); it goes to their mailbox and is not stored by Vanimo."""
    async with user_tx(state.engine, user) as conn:
        settings = await load_settings(conn)
        d = (
            await conn.execute(
                text("select id, mode, reply_to_enc, checks, placed_state from vanimo.drafts where id = :id"),
                {"id": draft_id},
            )
        ).first()
    if d is None:
        raise DraftError("not_found", 404)
    if not settings.allowed_by_organisation:
        raise DraftError("server_drafts_off", 403)
    if d.mode != "reply" or not d.reply_to_enc:
        raise DraftError("reply_drafts_only", 409)
    if d.placed_state == "placed":
        raise DraftError("already_placed", 409)
    if any(c.get("severity") == "block" for c in d.checks) and not confirmed:
        raise DraftError("confirmation_required", 409)
    if not text_shown.strip():
        raise DraftError("empty_draft", 422)
    reply_to = state.vault.decrypt_user(user.tenant_id, user.user_id, d.reply_to_enc, "draft_reply_to") or ""
    placed = await source.create_reply_draft(reply_to, text_shown, reply_all=False)
    t, u = user.tenant_id, user.user_id
    async with user_tx(state.engine, user) as conn:
        await conn.execute(
            text(
                "update vanimo.drafts set placed_ref_enc = :r, placed_link_enc = :l, placed_at = now(), "
                "placed_state = 'placed' where id = :id"
            ),
            {
                "r": state.vault.encrypt_user(t, u, placed.id, "draft_placed"),
                "l": state.vault.encrypt_user(t, u, placed.web_link, "draft_link"),
                "id": draft_id,
            },
        )
        await audit.record(conn, user, "draft.placed", target_kind="draft", target_ref=draft_id, request_id=request_id)
    return {"placed": True, "webLink": placed.web_link}


async def tidy(state: AppState, user: UserRef, source: WorkspaceSource) -> dict[str, int]:
    """Clean up placed drafts nobody used (see the module docstring). Returns content-free counts."""
    hasher = hasher_for(state.vault, user)
    async with user_tx(state.engine, user) as conn:
        settings = await load_settings(conn)
        rows = (
            await conn.execute(
                text(
                    "select id, thread_hash, placed_ref_enc, placed_at from vanimo.drafts "
                    "where placed_state = 'placed' and source_kind = :k"
                ),
                {"k": source.kind},
            )
        ).all()
    if not rows:
        return {}
    now = datetime.now(UTC)
    replied: dict[str, datetime] = {}
    for h in await source.recent_sent(50):
        th = hasher("thread", h.conversation_id)
        replied[th] = max(h.sent_at, replied.get(th, h.sent_at))
    counts: dict[str, int] = {}
    for r in rows:
        item_id = state.vault.decrypt_user(user.tenant_id, user.user_id, r.placed_ref_enc, "draft_placed") or ""
        stale = r.placed_at < now - timedelta(days=settings.stale_days)
        answered = r.thread_hash in replied and replied[r.thread_hash] > r.placed_at
        if not (stale or answered):
            continue
        item = await source.draft_state(item_id)
        if not item.exists:
            new_state = "gone"
        elif not item.is_draft:
            new_state = "sent"
        elif item.modified_at is not None and item.modified_at > r.placed_at + EDIT_GRACE:
            new_state = "kept_edited"
        elif await source.delete_draft(item_id):
            new_state = "replaced" if answered else "removed_stale"
        else:
            new_state = "gone"
        async with user_tx(state.engine, user) as conn:
            await conn.execute(
                text("update vanimo.drafts set placed_state = :s where id = :id"), {"s": new_state, "id": r.id}
            )
        counts[new_state] = counts.get(new_state, 0) + 1
    if counts:
        log.info("queue.tidy", count=sum(counts.values()))
    return counts
