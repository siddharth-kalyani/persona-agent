"""Thin async Microsoft Graph client with throttling-aware retries.

Errors expose only the HTTP status and Graph's error *code* and inner-error code (never the
message, which can echo request data). Nothing here logs URLs, query strings or response bodies.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator, Mapping
from typing import Any

import httpx

from vanimo.logs import get_logger

log = get_logger("vanimo.graph")

RETRY_STATUSES = frozenset({429, 502, 503, 504})


class GraphError(Exception):
    def __init__(self, status: int, code: str, inner: str = "") -> None:
        super().__init__(f"graph {status} {code}")
        self.status = status
        self.code = code
        # innerError.code: what some APIs branch on (transcripts: GraphAccessToTranscriptsDisabled,
        # SpeakerAttributionNotAllowed under a plain "Forbidden").
        self.inner = inner


class GraphClient:
    def __init__(
        self,
        token: str,
        http: httpx.AsyncClient,
        base_url: str = "https://graph.microsoft.com/v1.0",
        *,
        max_attempts: int = 4,
        max_backoff_s: float = 30.0,
        max_concurrency: int | None = None,
    ) -> None:
        self._token = token
        self._http = http
        self._base = base_url.rstrip("/")
        self._max_attempts = max_attempts
        self._max_backoff = max_backoff_s
        # Exchange allows 4 concurrent requests per app per mailbox; stay below it.
        self._sem = asyncio.Semaphore(max_concurrency) if max_concurrency else None

    def _url(self, path_or_url: str) -> str:
        if path_or_url.startswith("https://graph.microsoft.com/"):
            return path_or_url  # @odata.nextLink / deltaLink
        if path_or_url.startswith("http"):
            raise ValueError("refusing to call a non-Graph URL")
        return f"{self._base}/{path_or_url.lstrip('/')}"

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        json: Any = None,
        headers: Mapping[str, str] | None = None,
        idempotent: bool = True,
    ) -> httpx.Response:
        hdrs = {"Authorization": f"Bearer {self._token}", **(headers or {})}
        url = self._url(path)
        for attempt in range(1, self._max_attempts + 1):
            if self._sem is None:
                resp = await self._http.request(method, url, params=params, json=json, headers=hdrs)
            else:
                async with self._sem:
                    resp = await self._http.request(method, url, params=params, json=json, headers=hdrs)
            if resp.status_code not in RETRY_STATUSES or attempt == self._max_attempts:
                break
            if not idempotent and resp.status_code != 429:
                break  # a 5xx may have done the work (a draft created): never repeat a non-idempotent call
            retry_after = _retry_after(resp, attempt, self._max_backoff)
            log.warning("graph.retry", graph_status=resp.status_code, attempt=attempt, retry_after_s=retry_after)
            await asyncio.sleep(retry_after)
        if resp.is_success:
            return resp
        code, inner = _error_codes(resp)
        log.info("graph.error", graph_status=resp.status_code, graph_code=code)
        raise GraphError(resp.status_code, code, inner)

    def for_background(self) -> GraphClient:
        """Same token, patient retries: for long passes that run outside a request."""
        return GraphClient(self._token, self._http, self._base, max_attempts=8, max_backoff_s=60)

    async def get(self, path: str, params: Mapping[str, str] | None = None, **kw: Any) -> dict[str, Any]:
        return (await self.request("GET", path, params=params, **kw)).json()

    async def post(self, path: str, json: Any = None, **kw: Any) -> dict[str, Any]:
        resp = await self.request("POST", path, json=json, **kw)
        return resp.json() if resp.content else {}

    async def patch(self, path: str, json: Any = None, **kw: Any) -> dict[str, Any]:
        resp = await self.request("PATCH", path, json=json, **kw)
        return resp.json() if resp.content else {}

    async def delete(self, path: str) -> None:
        await self.request("DELETE", path)

    async def pages(
        self, path: str, params: Mapping[str, str] | None = None, *, max_pages: int = 50, **kw: Any
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield each page; follows @odata.nextLink. The last page may carry @odata.deltaLink."""
        page = await self.get(path, params, **kw)
        yield page
        for _ in range(max_pages - 1):
            nxt = page.get("@odata.nextLink")
            if not nxt:
                return
            page = await self.get(nxt, **kw)
            yield page


def _retry_after(resp: httpx.Response, attempt: int, cap: float) -> float:
    header = resp.headers.get("Retry-After")
    if header and header.isdigit():
        return min(float(header), cap)
    return min(cap, (2 ** (attempt - 1)) + random.uniform(0, 0.5))  # noqa: S311 - jitter, not crypto


def _safe_code(code: Any) -> str:
    code = str(code or "")
    return code if code.replace("_", "").replace(".", "").isalnum() and len(code) <= 80 else "unknown"


def _error_codes(resp: httpx.Response) -> tuple[str, str]:
    try:
        error = resp.json().get("error", {}) or {}
    except (ValueError, AttributeError):
        return "unknown", ""
    if not isinstance(error, dict):
        return "unknown", ""
    inner = error.get("innerError") or error.get("innererror") or {}
    inner_code = inner.get("code") if isinstance(inner, dict) else None
    return _safe_code(error.get("code")), _safe_code(inner_code) if inner_code else ""
