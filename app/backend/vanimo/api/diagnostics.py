"""Admin diagnostics: the week-1 spikes (docs/05 §5) as repeatable, content-free checks.

Every result is counts, booleans, timings, HTTP statuses and Graph error codes — never
subjects, names, message text or IDs. No check reads message content: the onboarding gate
(`vanimo.gates`) forbids that before the user's review, and diagnostics are no exception.
The same checks become the admin "live health checks" (transcript access etc.) in M6.

Responses must finish inside CloudFront's 60 s origin timeout, so checks run concurrently,
each with its own deadline, and Graph retries use a short backoff.
"""

from __future__ import annotations

import asyncio
import re
import statistics
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from vanimo import audit
from vanimo.api.deps import AdminPrincipal, CurrentUser, State, UserGraph
from vanimo.db.session import UserRef, user_tx
from vanimo.graph import metadata
from vanimo.graph.client import GraphClient, GraphError
from vanimo.logs import get_logger
from vanimo.state import AppState

log = get_logger("vanimo.diagnostics")
router = APIRouter(prefix="/api/admin/diagnostics", tags=["diagnostics"])

Outcome = Literal["ok", "warn", "fail", "skipped"]
Detail = int | float | bool | str | None
CheckFn = Callable[[], Awaitable[tuple[Outcome, dict[str, Detail]]]]

CHECK_DEADLINE_S = 25.0
HEADER_PASS_BUDGET_S = 45.0
LATENCY_BUDGET_S = 45.0
FORWARD_PREFIX = re.compile(r"^\s*(fw|fwd)\s*:", re.IGNORECASE)


class CheckResult(BaseModel):
    check: str
    outcome: Outcome
    durationMs: float
    details: dict[str, Detail] = Field(default_factory=dict)


class RunResponse(BaseModel):
    results: list[CheckResult]


def _enabled(state: AppState) -> None:
    if not state.settings.enable_diagnostics:
        raise HTTPException(404)


async def _audit(state: AppState, user: UserRef, action: str, request: Request, **kw: Any) -> None:
    async with user_tx(state.engine, user) as conn:
        await audit.record(conn, user, action, request_id=request.state.request_id, **kw)


async def _timed(name: str, fn: CheckFn, deadline_s: float = CHECK_DEADLINE_S) -> CheckResult:
    start = time.perf_counter()
    try:
        outcome, details = await asyncio.wait_for(fn(), deadline_s)
    except TimeoutError:
        outcome, details = "fail", {"error_type": "deadline_exceeded", "deadline_s": deadline_s}
    except GraphError as exc:
        outcome, details = "fail", {"graph_status": exc.status, "graph_code": exc.code}
    except Exception as exc:
        outcome, details = "fail", {"error_type": type(exc).__name__}
    ms = round((time.perf_counter() - start) * 1000, 1)
    log.info("diagnostics.check", check=name, outcome=outcome, duration_ms=ms)
    return CheckResult(check=name, outcome=outcome, durationMs=ms, details=details)


async def check_profile(graph: GraphClient) -> tuple[Outcome, dict[str, Detail]]:
    me = await metadata.me(graph)
    mgr = await metadata.manager(graph)
    return "ok", {"has_job_title": bool(me.get("jobTitle")), "manager_found": mgr is not None}


async def check_sent_headers(graph: GraphClient) -> tuple[Outcome, dict[str, Detail]]:
    """Spike 3 (MSIP labels on Sent Items) + spike 11 (conversationId on forwards). Headers only."""
    page = await graph.get(
        "me/mailFolders/sentitems/messages",
        {
            "$select": metadata.assert_metadata_only(("id", "subject", "conversationId", "internetMessageHeaders")),
            "$top": "50",
            "$orderby": "sentDateTime desc",
        },
    )
    items = page.get("value", [])
    with_headers = [m for m in items if m.get("internetMessageHeaders")]
    labelled = sum(
        1
        for m in with_headers
        if any((h.get("name") or "").lower() == "msip_labels" for h in m["internetMessageHeaders"])
    )
    forwards = [m for m in items if FORWARD_PREFIX.match(m.get("subject") or "")]
    return "ok", {
        "items": len(items),
        "with_internet_headers": len(with_headers),
        "with_msip_labels": labelled,
        "forwards": len(forwards),
        "forwards_with_conversation_id": sum(1 for m in forwards if m.get("conversationId")),
    }


async def check_sent_delta(graph: GraphClient) -> tuple[Outcome, dict[str, Detail]]:
    pages = items = 0
    reached_delta = False
    async for page in graph.pages(
        "me/mailFolders/sentitems/messages/delta",
        {"$select": metadata.assert_metadata_only(metadata.SENT_HEADER_FIELDS)},
        max_pages=3,
        headers={"Prefer": "odata.maxpagesize=50"},
    ):
        pages += 1
        items += len(page.get("value", []))
        reached_delta = "@odata.deltaLink" in page
    return "ok", {"pages": pages, "items": items, "reached_delta_link_in_3_pages": reached_delta}


async def check_chats(graph: GraphClient) -> tuple[Outcome, dict[str, Detail]]:
    page = await graph.get("me/chats", {"$expand": "members", "$top": "50"})
    chats = page.get("value", [])
    kinds = Counter(c.get("chatType", "unknown") for c in chats)
    details: dict[str, Detail] = {
        "chats_first_page": len(chats),
        "has_more": "@odata.nextLink" in page,
        "with_topic": sum(1 for c in chats if c.get("topic")),
        "max_members": max((len(c.get("members") or []) for c in chats), default=0),
        **{f"type_{k}": v for k, v in sorted(kinds.items())},
    }
    for name, flt in (("filter_chat_type", "chatType eq 'group'"), ("filter_topic", "topic ne null")):
        try:
            await graph.get("me/chats", {"$filter": flt, "$top": "1"})
            details[f"{name}_supported"] = True
        except GraphError as exc:
            details[f"{name}_supported"] = False
            details[f"{name}_status"] = exc.status
    return "ok", details


async def _recent_online_meetings(graph: GraphClient) -> list[dict[str, Any]]:
    end = datetime.now(UTC)
    start = end - timedelta(days=14)
    page = await graph.get(
        "me/calendarView",
        {
            "startDateTime": start.isoformat(),
            "endDateTime": end.isoformat(),
            "$select": "id,isOnlineMeeting,isOrganizer,sensitivity,onlineMeeting",
            "$top": "50",
            "$orderby": "start/dateTime desc",
        },
    )
    return list(page.get("value", []))


async def check_calendar(graph: GraphClient) -> tuple[Outcome, dict[str, Detail]]:
    events = await _recent_online_meetings(graph)
    return "ok", {
        "events_14d": len(events),
        "online_meetings": sum(1 for e in events if e.get("isOnlineMeeting")),
        "organized_by_me": sum(1 for e in events if e.get("isOrganizer")),
        "private": sum(1 for e in events if e.get("sensitivity") == "private"),
    }


def _odata_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


async def check_transcripts(graph: GraphClient) -> tuple[Outcome, dict[str, Detail]]:
    """Spike 4 + "non-organiser access": can we list transcripts as organiser / attendee?

    Lists transcript metadata only; transcript content is never downloaded here.
    """
    events = [
        e
        for e in await _recent_online_meetings(graph)
        if e.get("isOnlineMeeting") and (e.get("onlineMeeting") or {}).get("joinUrl")
    ][:6]
    if not events:
        return "skipped", {"reason": "no_online_meetings_14d"}
    tally: Counter[str] = Counter()
    codes: Counter[str] = Counter()
    for e in events:
        role = "organizer" if e.get("isOrganizer") else "attendee"
        try:
            found = await graph.get(
                "me/onlineMeetings",
                {"$filter": f"JoinWebUrl eq {_odata_quote(e['onlineMeeting']['joinUrl'])}", "$select": "id"},
            )
            meetings = found.get("value", [])
            if not meetings:
                tally[f"{role}_lookup_empty"] += 1
                continue
            tr = await graph.get(f"me/onlineMeetings/{meetings[0]['id']}/transcripts", {"$select": "id"})
            tally[f"{role}_transcripts_listed"] += 1
            tally[f"{role}_transcripts_found"] += len(tr.get("value", []))
        except GraphError as exc:
            tally[f"{role}_error"] += 1
            codes[f"{exc.status}:{exc.code}"] += 1
    details: dict[str, Detail] = {"meetings_checked": len(events), **dict(tally)}
    details.update({f"code_{i}": f"{c} x{n}" for i, (c, n) in enumerate(codes.most_common(3))})
    listed = tally["attendee_transcripts_listed"] or tally["organizer_transcripts_listed"]
    return ("ok" if listed else "warn"), details


@router.post("/run", response_model=RunResponse)
async def run_checks(
    _: AdminPrincipal, user: CurrentUser, graph: UserGraph, state: State, request: Request
) -> RunResponse:
    _enabled(state)
    checks: list[tuple[str, CheckFn]] = [
        ("graph_profile", lambda: check_profile(graph)),
        ("sent_headers", lambda: check_sent_headers(graph)),
        ("sent_delta_headers", lambda: check_sent_delta(graph)),
        ("chats_roster", lambda: check_chats(graph)),
        ("calendar", lambda: check_calendar(graph)),
        ("meeting_transcripts", lambda: check_transcripts(graph)),
    ]
    results = await asyncio.gather(*(_timed(name, fn) for name, fn in checks))
    await _audit(state, user, "diagnostics.run", request)
    return RunResponse(results=list(results))


class HeaderPassOut(BaseModel):
    sentItems: int
    sentPages: int
    sentFinished: bool
    chats: int
    chatPages: int
    chatsFinished: bool
    elapsedMs: float
    itemsPerSecond: float | None


@router.post("/header-pass", response_model=HeaderPassOut)
async def header_pass_timing(
    _: AdminPrincipal, user: CurrentUser, graph: UserGraph, state: State, request: Request
) -> HeaderPassOut:
    """Spike 11: how long the M1 header pass takes for this mailbox (sent headers + chat roster).

    Runs for at most ~45 s; if it doesn't finish, the rate lets you extrapolate. Counts only.
    """
    _enabled(state)
    start = time.perf_counter()
    deadline = start + HEADER_PASS_BUDGET_S
    sent = {"items": 0, "pages": 0, "done": False}
    chats = {"items": 0, "pages": 0, "done": False}

    async def walk(path: str, params: dict[str, str], headers: dict[str, str], acc: dict[str, Any]) -> None:
        async for page in graph.pages(path, params, max_pages=10_000, headers=headers):
            acc["pages"] += 1
            acc["items"] += len(page.get("value", []))
            if "@odata.deltaLink" in page or "@odata.nextLink" not in page:
                acc["done"] = True

    # Counts accumulate as pages arrive, so stopping at the budget (even mid-page) keeps them.
    walks = [
        asyncio.ensure_future(w)
        for w in (
            walk(
                "me/mailFolders/sentitems/messages/delta",
                {"$select": metadata.assert_metadata_only(metadata.SENT_HEADER_FIELDS)},
                {"Prefer": "odata.maxpagesize=100"},
                sent,
            ),
            walk("me/chats", {"$expand": "members", "$top": "50"}, {}, chats),
        )
    ]
    _, pending = await asyncio.wait(walks, timeout=max(0.0, deadline - time.perf_counter()))
    for task in pending:
        task.cancel()
    await asyncio.gather(*walks, return_exceptions=True)
    for task in walks:  # a Graph failure (not our own cancellation) is reported, not hidden
        if not task.cancelled() and task.exception() is not None:
            raise task.exception()  # type: ignore[misc]
    elapsed = time.perf_counter() - start
    await _audit(state, user, "diagnostics.header_pass", request)
    return HeaderPassOut(
        sentItems=sent["items"],
        sentPages=sent["pages"],
        sentFinished=sent["done"],
        chats=chats["items"],
        chatPages=chats["pages"],
        chatsFinished=chats["done"],
        elapsedMs=round(elapsed * 1000, 1),
        itemsPerSecond=round(sent["items"] / elapsed, 1) if elapsed > 0 else None,
    )


class LatencyRequest(BaseModel):
    runs: int = Field(default=5, ge=1, le=5)


class LatencyResult(BaseModel):
    modelId: str
    runs: int
    errors: int
    ttftMinMs: float | None
    ttftMedianMs: float | None
    ttftMaxMs: float | None
    totalMedianMs: float | None
    errorTypes: list[str]


@router.post("/bedrock-latency", response_model=list[LatencyResult])
async def bedrock_latency(
    body: LatencyRequest, _: AdminPrincipal, user: CurrentUser, state: State, request: Request
) -> list[LatencyResult]:
    """Spike 7: first-token latency from this cell to each allowed model (synthetic prompt).

    A handful of samples gives min/median/max, not a p95 — the real p95 comes from drafting
    traffic in M3. Models are measured concurrently to stay inside the edge timeout.
    """
    _enabled(state)
    deadline = time.perf_counter() + LATENCY_BUDGET_S

    async def measure(model: str) -> LatencyResult:
        ttfts: list[float] = []
        totals: list[float] = []
        errors: Counter[str] = Counter()
        for _ in range(body.runs):
            remaining = deadline - time.perf_counter()
            if remaining <= 1:
                errors["budget_exhausted"] += 1
                continue
            try:
                probe = state.llm.timed_probe(model, "Reply with the single word: ready")
                t = await asyncio.wait_for(probe, min(20.0, remaining))
                if t.ttft_ms is not None:
                    ttfts.append(t.ttft_ms)
                totals.append(t.total_ms)
            except Exception as exc:
                errors[type(exc).__name__] += 1
        log.info("diagnostics.bedrock_latency", model_id=model, count=len(ttfts))
        return LatencyResult(
            modelId=model,
            runs=body.runs,
            errors=sum(errors.values()),
            ttftMinMs=min(ttfts) if ttfts else None,
            ttftMedianMs=round(statistics.median(ttfts), 1) if ttfts else None,
            ttftMaxMs=max(ttfts) if ttfts else None,
            totalMedianMs=round(statistics.median(totals), 1) if totals else None,
            errorTypes=sorted(errors),
        )

    results = await asyncio.gather(*(measure(m) for m in state.settings.cell_config.model_allow_list))
    await _audit(state, user, "diagnostics.bedrock_latency", request)
    return list(results)


# Graph message IDs are URL-safe base64; anything else could inject path segments.
GRAPH_ID = re.compile(r"[A-Za-z0-9_=\-]{1,512}")
DRAFT_PROBE_COMMENT = "Vanimo M0 test draft (safe to delete). Created by the admin diagnostics page."


class DraftProbeOut(BaseModel):
    draftId: str
    webLink: str | None


@router.post("/draft-probe", response_model=DraftProbeOut)
async def create_draft_probe(
    _: AdminPrincipal, user: CurrentUser, graph: UserGraph, state: State, request: Request
) -> DraftProbeOut:
    """Spike 5: does a Graph `createReply` draft show up in Outlook mobile's Drafts folder?"""
    _enabled(state)
    inbox = await graph.get(
        "me/mailFolders/inbox/messages", {"$select": "id", "$top": "1", "$orderby": "receivedDateTime desc"}
    )
    if not inbox.get("value"):
        raise HTTPException(409, detail={"error": "inbox_empty"})
    draft = await graph.post(
        f"me/messages/{inbox['value'][0]['id']}/createReply", json={"comment": DRAFT_PROBE_COMMENT}
    )
    ref = audit.opaque_ref(state.settings.ref_hmac_key.get_secret_value(), draft["id"])
    await _audit(state, user, "diagnostics.draft_probe.created", request, target_kind="draft", target_ref=ref)
    return DraftProbeOut(draftId=draft["id"], webLink=draft.get("webLink"))


@router.delete("/draft-probe/{draft_id}", status_code=204)
async def delete_draft_probe(
    draft_id: str, _: AdminPrincipal, user: CurrentUser, graph: UserGraph, state: State, request: Request
) -> None:
    """Deletes only drafts this page created (checked against the caller's own audit log)."""
    _enabled(state)
    if not GRAPH_ID.fullmatch(draft_id):
        raise HTTPException(422, detail={"error": "invalid_id"})
    ref = audit.opaque_ref(state.settings.ref_hmac_key.get_secret_value(), draft_id)
    async with user_tx(state.engine, user) as conn:
        if not await audit.has_event(conn, "diagnostics.draft_probe.created", ref):
            raise HTTPException(404, detail={"error": "not_a_probe_draft"})
    await graph.delete(f"me/messages/{draft_id}")
    await _audit(state, user, "diagnostics.draft_probe.deleted", request, target_kind="draft", target_ref=ref)
