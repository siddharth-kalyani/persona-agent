"""The drafting service (MVP plan M3; architecture §7.2 S12, §9.1-§9.2).

    rate limit → onboarding gate → exclusions on the conversation or chat (metadata) → live thread to L1
    → persona pack (exemplars post-filtered) → model route → generate the body → output gate
    → greeting + body + sign-off → re-hydrate for the owner → pre-send checks → store (L1)

Nothing is ever sent: the draft goes back to the user's screen. Logs carry codes, counts and
timings only. Emails (M3) and Teams chats (M5) go through the same steps; a chat has no subject,
greeting or sign-off, and its roster is what the exclusion engine decides on.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from vanimo import audit
from vanimo.controls.neversend import Matcher, Term, render_removed
from vanimo.controls.store import hasher_for, load_engine, load_terms, lock_user_controls
from vanimo.db.session import UserRef, user_tx
from vanimo.drafting import checks as chk
from vanimo.drafting.checks import Check, ClientAccount
from vanimo.drafting.context import Audience, DraftError, LiveContext, Mode, gather, gather_chat
from vanimo.drafting.gate import compose, gate, render
from vanimo.drafting.generate import OFFLINE_LABEL, BedrockGenerator, Generator, OfflineGenerator
from vanimo.drafting.pack import load_pack
from vanimo.drafting.prompt import apply_rules, build
from vanimo.gates import onboarding_state
from vanimo.learning import style
from vanimo.learning.backfill import controls_version
from vanimo.llm.router import Quality
from vanimo.logs import get_logger
from vanimo.redaction.marks import L1_MARKS
from vanimo.redaction.pipeline import Person
from vanimo.sources.base import Address, WorkspaceSource
from vanimo.state import AppState

log = get_logger("vanimo.drafting")

MAX_CHECK_CHARS = 20_000  # of your own words, after the quoted thread is cut off


@dataclass
class DraftInput:
    mode: Mode
    surface: Literal["outlook", "web", "queue", "teams", "commitments"]
    conversation_id: str | None = None  # an email conversation, or the chat ID for a Teams draft
    to: list[Address] | None = None
    cc: list[Address] | None = None
    subject: str | None = None
    instruction: str | None = None
    quality: Quality = "auto"
    reply_all: bool = False
    one_off: bool = False
    channel: Literal["email", "chat"] = "email"
    message_id: str | None = None  # Teams: the chat message being answered


@dataclass
class DraftResult:
    id: str | None
    text: str
    generator: str
    label: str
    model_id: str
    tier: str
    route_reason: str
    audience: Audience
    card_key: str | None
    learned: bool
    based_on: int
    exemplars: int
    checks: list[Check]
    one_off: bool
    total_ms: float
    model_ms: float | None
    extra: dict[str, Any] = field(default_factory=dict)
    channel: str = "email"
    chat_users: list[str] = field(default_factory=list)  # Teams: who "Open chat" opens it with

    @property
    def insert_allowed(self) -> bool:
        return not chk.blocked(self.checks)


def _sample_domains(source: WorkspaceSource) -> frozenset[str]:
    from vanimo.sources.sample import ORG_DOMAIN

    return frozenset({ORG_DOMAIN}) if source.kind == "sample" else frozenset()


async def _known(conn: AsyncConnection, state: AppState, user: UserRef) -> tuple[set[str], list[Person]]:
    """From the user's Sources index: the domains they've corresponded with (the look-alike test)
    and the people, so drafting tokenises the same names the learner does."""
    t, u = user.tenant_id, user.user_id
    domains: set[str] = set()
    people: list[Person] = []
    for r in (await conn.execute(text("select email_enc, name_enc, domain_enc from vanimo.source_people"))).all():
        domain = state.vault.decrypt_user(t, u, r.domain_enc, "domain")
        if domain:
            domains.add(domain.lower())
        name = state.vault.decrypt_user(t, u, r.name_enc, "name")
        email = state.vault.decrypt_user(t, u, r.email_enc, "email")
        if name and email:
            people.append(Person(name, email.lower()))
    return domains, people


async def _client_accounts(conn: AsyncConnection, state: AppState, user: UserRef) -> list[ClientAccount]:
    accounts = (await conn.execute(text("select id, name_enc from vanimo.client_accounts"))).all()
    hashes: dict[str, set[str]] = {}
    for r in (await conn.execute(text("select account_id, domain_hash from vanimo.client_account_domains"))).all():
        hashes.setdefault(str(r.account_id), set()).add(r.domain_hash)
    return [
        ClientAccount(
            state.vault.decrypt_tenant(user.tenant_id, a.name_enc, "account_name") or "",
            frozenset(hashes.get(str(a.id), ())),
        )
        for a in accounts
    ]


PREMIUM_EVENT = "draft.premium_used"


async def premium_used(conn: AsyncConnection) -> int:
    """Sonnet drafts in the last 24 hours, from the append-only audit log (content-free), so one-off
    drafts count and deleting drafts doesn't reset the quota."""
    return (
        await conn.execute(
            text(
                "select count(*) from vanimo.audit_events where action = :a and occurred_at > now() - interval '1 day'"
            ),
            {"a": PREMIUM_EVENT},
        )
    ).scalar_one()


async def require_review(state: AppState, user: UserRef, source: WorkspaceSource) -> None:
    async with user_tx(state.engine, user) as conn:
        onboarding, _ = await onboarding_state(conn, source.kind)
    if onboarding != "review_done":
        raise DraftError("review_pending", 409)


def generator_for(state: AppState) -> Generator:
    return BedrockGenerator(state.llm) if state.settings.drafter == "bedrock" else OfflineGenerator()


async def create_draft(
    state: AppState, user: UserRef, source: WorkspaceSource, *, self_email: str, req: DraftInput, request_id: str
) -> DraftResult:
    start = time.perf_counter()
    settings = state.settings
    state.draft_throttle.check(
        str(user.user_id), per_minute=settings.drafts_per_minute, per_day=settings.drafts_per_day
    )
    if req.mode == "new" and not (req.instruction and req.instruction.strip()):
        raise DraftError("instruction_required", 422)
    if req.channel == "chat" and not req.conversation_id:
        raise DraftError("chat_required", 422)
    await require_review(state, user, source)

    hasher = hasher_for(state.vault, user)
    sample_domains = _sample_domains(source)
    async with user_tx(state.engine, user) as conn:
        ex_engine = await load_engine(conn, state.vault, user, self_email=self_email, extra_org_domains=sample_domains)
        terms = await load_terms(conn, state.vault, user)
        used = await premium_used(conn)
        known, known_people = await _known(conn, state, user)
        accounts = await _client_accounts(conn, state, user)
        version = await controls_version(conn)
        meeting = await _chat_meeting(conn, hasher, req.conversation_id) if req.channel == "chat" else None
    matcher = Matcher([Term(t["term_id"], t["text"], t["kind"], tuple(t["variants"]), t["folds"]) for t in terms])
    blocked_matcher = Matcher(
        [
            Term(t["term_id"], t["text"], t["kind"], tuple(t["variants"]), t["folds"])
            for t in terms
            if not t["allow_in_drafts"]
        ]
    )
    allowed_terms = {t["term_id"]: t["text"] for t in terms if t["allow_in_drafts"]}

    directory = await state.directory_cache.get((str(user.user_id), source.kind), source, self_email)
    if req.channel == "chat":
        ctx = await gather_chat(
            source,
            ex_engine=ex_engine,
            matcher=matcher,
            hasher=hasher,
            directory=directory,
            self_email=self_email,
            chat_id=req.conversation_id or "",
            meeting=meeting,
            mode=req.mode,
            instruction=req.instruction,
            message_id=req.message_id,
            one_off=req.one_off,
            known_people=known_people,
        )
    else:
        ctx = await gather(
            source,
            ex_engine=ex_engine,
            matcher=matcher,
            hasher=hasher,
            directory=directory,
            self_email=self_email,
            mode=req.mode,
            conversation_id=req.conversation_id,
            to=req.to,
            cc=req.cc,
            subject=req.subject,
            instruction=req.instruction,
            reply_all=req.reply_all,
            one_off=req.one_off,
            known_people=known_people,
        )
    async with user_tx(state.engine, user) as conn:
        pack = await load_pack(conn, state.vault, user, source.kind, ctx, ex_engine, hasher, matcher)
    prompt = build(ctx, pack)
    route = state.router.route_draft(
        mode=req.mode,
        relationship=ctx.audience.relationship,
        target_words=prompt.target_words,
        quality=req.quality,
        premium_used_today=used,
    )
    generator = generator_for(state)
    try:
        body = await generator.body(ctx, pack, prompt, route)
    except DraftError:
        raise
    except Exception as exc:
        log.error("draft.model_failed", error_type=type(exc).__name__, model_id=route.model_id)
        raise DraftError("model_unavailable", 503) from None
    if generator.kind == "bedrock" and route.tier == "premium":
        async with user_tx(state.engine, user) as conn:
            await audit.record(conn, user, PREMIUM_EVENT, request_id=request_id)

    # Learned rules first, then the gate: whatever they change still passes every output check.
    gated = gate(apply_rules(body.text, prompt), prompt_marks=prompt.marks, grounding=ctx.grounding, matcher=matcher)
    if gated.blocked:
        log.warning("draft.blocked", error_code=gated.blocked)
        raise DraftError("draft_blocked", 422, reason=gated.blocked)
    l1 = compose(prompt.greeting, gated.body, prompt.sign_off)
    values = {**pack.stored_tokens, **ctx.tokens}
    shown, removed = render(
        l1, values=values, allowed_marks=prompt.marks, allowed_terms=allowed_terms, blocked_matcher=blocked_matcher
    )
    grounding, _ = render(
        ctx.grounding,
        values=values,
        allowed_marks=set(L1_MARKS.findall(ctx.grounding)),
        allowed_terms=allowed_terms,
        blocked_matcher=blocked_matcher,
    )
    received = [
        render(
            t, values=values, allowed_marks=set(L1_MARKS.findall(t)), allowed_terms={}, blocked_matcher=blocked_matcher
        )[0]
        for t in ctx.received
    ]
    org = set(directory.org_domains) | set(sample_domains)
    recipients = [r.address for r in ctx.audience.to + ctx.audience.cc]
    found: list[Check] = []
    found += chk.sender_lookalike(_senders(ctx), known_domains=known, org_domains=org)
    found += chk.reply_to_redirect(ctx.redirects, known_domains=known, org_domains=org)
    found += chk.payment_change(received, shown, sender_lookalike=chk.blocked(found))
    if ctx.channel == "email":  # a chat's members are its roster, not recipients the user picked
        found += chk.recipient_checks(
            recipients, thread_people=ctx.thread_people, known_domains=known, org_domains=org, me=self_email
        )
    found += chk.cross_client(shown, recipients, accounts, ex_engine.domain_hashes)
    found += chk.invented_facts(shown, grounding)
    found += chk.fill_ins(shown)
    if ctx.suspicious:
        found.append(
            Check(
                "hidden_content",
                "warn",
                f"The {'chat' if ctx.channel == 'chat' else 'email'} you're replying to had hidden text, which was "
                "removed before drafting. Hidden text is a common way to trick AI assistants.",
            )
        )
    found += gated.notes
    if removed:
        found.append(Check("never_send_removed", "info", f"{removed} never-send word(s) show as [removed]."))
    if not pack.learned:
        found.append(
            Check(
                "persona_not_learned",
                "info",
                "Vanimo hasn't learned your style yet: run Learning for drafts in your voice.",
            )
        )
    if ctx.one_off:
        found.append(
            Check(
                "one_off",
                "info",
                "You excluded this conversation. This draft was made once, in memory, and isn't saved.",
            )
        )
    found = list({c.code: c for c in found}.values())  # one of each

    draft_id: str | None = None
    total_ms = round((time.perf_counter() - start) * 1000, 1)
    model_id = route.model_id
    if not ctx.one_off:
        draft_id = await _store(
            state,
            user,
            source,
            ctx,
            req,
            l1,
            route.tier,
            model_id,
            generator.kind,
            found,
            total_ms,
            hasher,
            ex_engine,
            request_id,
            version,
        )
        if draft_id is None:
            # A rule or never-send word was added while drafting (§6.5 X4: it wins). The draft isn't
            # stored, and what's shown is masked again with the words as they are now.
            async with user_tx(state.engine, user) as conn:
                now_terms = await load_terms(conn, state.vault, user)
            now_blocked = Matcher(
                [
                    Term(t["term_id"], t["text"], t["kind"], tuple(t["variants"]), t["folds"])
                    for t in now_terms
                    if not t["allow_in_drafts"]
                ]
            )
            shown = render_removed(now_blocked.mask(shown)[0]) or ""
            found.append(
                Check(
                    "controls_changed",
                    "info",
                    "Your data controls changed while this draft was being written, so it wasn't saved.",
                )
            )
    log.info(
        "draft.done",
        generator=generator.kind,
        tier=route.tier,
        model_id=model_id,
        total_ms=total_ms,
        count=len(found),
        outcome="blocked_insert" if chk.blocked(found) else "ok",
    )
    return DraftResult(
        id=draft_id,
        text=shown,
        generator=generator.kind,
        label=OFFLINE_LABEL if generator.kind == "offline" else f"Claude ({model_id})",
        model_id=model_id,
        tier=route.tier,
        route_reason=route.reason,
        audience=ctx.audience,
        card_key=pack.card_key,
        learned=pack.learned,
        based_on=int(pack.card.get("n", 0)),
        exemplars=len(pack.exemplars),
        checks=found,
        one_off=ctx.one_off,
        total_ms=total_ms,
        model_ms=body.total_ms if generator.kind == "bedrock" else None,
        channel=ctx.channel,
        chat_users=[r.address.email for r in ctx.audience.to] if ctx.channel == "chat" else [],
    )


async def _chat_meeting(
    conn: AsyncConnection, hasher: Any, chat_id: str | None
) -> tuple[str | None, str | None] | None:
    """A meeting chat's meeting and series, as the header pass linked them (by the join link)."""
    if not chat_id:
        return None
    row = (
        await conn.execute(
            text("select chat_type, meeting_hash, series_hash from vanimo.source_chats where key_hash = :h"),
            {"h": hasher("chat", chat_id)},
        )
    ).first()
    if row is None or row.chat_type != "meeting" or not row.meeting_hash:
        return None
    return row.meeting_hash, row.series_hash


def _senders(ctx: LiveContext) -> list[Address]:
    """People who wrote to the user in this thread (the look-alike sender test)."""
    me = ctx.me.address.email
    return [a for a in ctx.thread_people if a.email and a.email.lower() != me][:20]


async def _store(
    state: AppState,
    user: UserRef,
    source: WorkspaceSource,
    ctx: LiveContext,
    req: DraftInput,
    l1: str,
    tier: str,
    model_id: str,
    generator: str,
    found: list[Check],
    total_ms: float,
    hasher: Any,
    ex_engine: Any,
    request_id: str,
    version: int,
) -> str | None:
    """Stores the draft unless the user's controls changed since drafting began (then None)."""
    me = ctx.me.address.email
    people = {
        a.email.lower(): a
        for a in [*ctx.thread_people, *(r.address for r in ctx.audience.to + ctx.audience.cc)]
        if a.email and a.email.lower() != me
    }
    lineage = [{"p": hasher("person", e), "d": ex_engine.domain_hashes(a.domain)} for e, a in sorted(people.items())]
    t, u = user.tenant_id, user.user_id
    async with user_tx(state.engine, user) as conn:
        await lock_user_controls(conn, user)  # serialised with purges and scrubs
        if await controls_version(conn) != version:
            return None
        draft_id = str(
            (
                await conn.execute(
                    text(
                        "insert into vanimo.drafts (tenant_id, owner_user_id, source_kind, surface, mode, generator, "
                        "tier, model_id, relationship, thread_hash, people, text_enc, checks, word_count, latency_ms, "
                        "reply_to_enc, audience_enc, channel, meeting_hash, series_hash, chat_ref_enc) "
                        "values (:t, :u, :k, :surface, :mode, :gen, :tier, :model, :rel, :th, cast(:people as jsonb), "
                        ":txt, "
                        "cast(:checks as jsonb), :wc, :ms, :rt, :aud, :ch, :mh, :sh, :cr) returning id"
                    ),
                    {
                        "t": t,
                        "u": u,
                        "k": source.kind,
                        "surface": req.surface,
                        "mode": req.mode,
                        "gen": generator,
                        "tier": tier,
                        "model": model_id,
                        "rel": ctx.audience.relationship,
                        "th": hasher("chat" if ctx.channel == "chat" else "thread", ctx.conversation_id)
                        if ctx.conversation_id
                        else None,
                        "ch": ctx.channel,
                        "mh": ctx.meeting_hash,
                        "sh": ctx.series_hash,
                        # The chat itself, so the Teams edit loop can find the message the user sent.
                        "cr": state.vault.encrypt_user(t, u, ctx.conversation_id, "draft_chat")
                        if ctx.channel == "chat"
                        else None,
                        "people": json.dumps(lineage),
                        "txt": state.vault.encrypt_user(t, u, l1, "draft_text"),
                        "checks": json.dumps([{"code": c.code, "severity": c.severity} for c in found]),
                        "wc": len(style._words(l1)),
                        "ms": int(total_ms),
                        # The people Vanimo checked: a draft put in Outlook is addressed to exactly them.
                        "aud": state.vault.encrypt_user(
                            t,
                            u,
                            json.dumps(
                                {
                                    side: [{"email": r.address.email, "name": r.address.name} for r in rs]
                                    for side, rs in (("to", ctx.audience.to), ("cc", ctx.audience.cc))
                                }
                            ),
                            "draft_audience",
                        ),
                        "rt": state.vault.encrypt_user(t, u, ctx.reply_to_id, "draft_reply_to")
                        if ctx.mode == "reply" and ctx.channel == "email"
                        else None,
                    },
                )
            ).scalar_one()
        )
        await audit.record(conn, user, "draft.created", target_kind="draft", target_ref=draft_id, request_id=request_id)
    return draft_id


# --- pre-send checks on the user's own text ------------------------------------------------------
async def check_text(
    state: AppState,
    user: UserRef,
    source: WorkspaceSource,
    *,
    self_email: str,
    body: str,
    to: list[Address],
    cc: list[Address],
    conversation_id: str | None,
) -> list[Check]:
    """Checks on what the user is about to send (their words, L0, in memory only). The thread is
    read only if the review is done and the conversation is allowed; an organisation-excluded
    conversation gets the recipient checks only."""
    from vanimo.redaction.parse import strip_quotes

    limits = state.settings
    state.draft_throttle.check(
        f"check:{user.user_id}", per_minute=limits.drafts_per_minute * 4, per_day=limits.drafts_per_day * 4
    )
    sample_domains = _sample_domains(source)
    async with user_tx(state.engine, user) as conn:
        onboarding, _ = await onboarding_state(conn, source.kind)
        ex_engine = await load_engine(conn, state.vault, user, self_email=self_email, extra_org_domains=sample_domains)
        terms = await load_terms(conn, state.vault, user)
        known, _ = await _known(conn, state, user)
        accounts = await _client_accounts(conn, state, user)
    directory = await state.directory_cache.get((str(user.user_id), source.kind), source, self_email)
    org = set(directory.org_domains) | set(sample_domains)
    me = self_email.lower()
    recipients = [a for a in [*to, *cc] if a.email and a.email.lower() != me]
    headers = []
    if conversation_id and onboarding == "review_done":
        from vanimo.drafting.context import _thread_headers

        headers = await _thread_headers(source, conversation_id)
        if headers:
            conversation_id = headers[0].conversation_id  # Graph's own form, as the rules use
    thread_people = [a for h in headers for a in h.participants]
    decision = ex_engine.conversation(conversation_id, [*thread_people, *recipients])
    found: list[Check] = []
    senders = [h.sender for h in headers if h.sender.email.lower() != me]
    found += chk.sender_lookalike(senders, known_domains=known, org_domains=org)
    redirects = [
        (h.sender, r)
        for h in headers
        for r in h.reply_to
        if r.email and r.email.lower() not in (h.sender.email.lower(), me)
    ]
    found += chk.reply_to_redirect(redirects, known_domains=known, org_domains=org)
    found += chk.recipient_checks(recipients, thread_people=thread_people, known_domains=known, org_domains=org, me=me)
    if decision.by_tenant:
        found.append(
            Check(
                "text_not_checked",
                "info",
                "This conversation is excluded by your organisation or includes someone Vanimo can't check, so only "
                "the recipients were checked.",
            )
        )
        return found
    own = strip_quotes(body)[0][:MAX_CHECK_CHARS]  # your words, not the quoted thread below them
    received: list[str] = []
    if headers and onboarding == "review_done" and not decision.excluded:
        last = [h for h in headers if h.direction == "received"][-2:]
        for h in last:
            m = await source.message(h.id)
            if m is not None:
                received.append(m.body[:4000])
    found += chk.payment_change(received, own, sender_lookalike=any(c.code == "lookalike_sender" for c in found))
    found += chk.greeting_mismatch(own, [a for a in to if a.email.lower() != me])
    found += chk.cross_client(own, recipients, accounts, ex_engine.domain_hashes)
    found += chk.regulated_ids(own)
    blocked_terms = Matcher(
        [
            Term(t["term_id"], t["text"], t["kind"], tuple(t["variants"]), t["folds"])
            for t in terms
            if not t["allow_in_drafts"]
        ]
    )
    if blocked_terms.count(own):
        found.append(Check("never_send_word", "warn", "This email contains a word from your never-send list."))
    return list({c.code: c for c in found}.values())
