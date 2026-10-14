"""FastAPI application factory.  Run locally: uv run uvicorn vanimo.main:app --reload"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from vanimo.api import admin_scoping, auth, controls, diagnostics, drafting, edits, learning, me, queue
from vanimo.auth.entra import AuthError
from vanimo.config import Settings, get_settings
from vanimo.controls.sweeper import sweep_forever
from vanimo.drafting.context import DraftError
from vanimo.graph.client import GraphError
from vanimo.logs import configure_logging, get_logger
from vanimo.state import AppState, build_state

log = get_logger("vanimo.http")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


def create_app(settings: Settings | None = None, state: AppState | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json=settings.env != "local")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.vanimo = state or build_state(settings)
        if settings.background_sweeper:
            app.state.vanimo.spawn(sweep_forever(app.state.vanimo.engine, app.state.vanimo.vault))
        log.info("app.start", env=settings.env, cell=settings.cell)
        try:
            yield
        finally:
            await app.state.vanimo.aclose()

    app = FastAPI(
        title="Vanimo API",
        version="0.1.0",
        lifespan=lifespan,
        # No interactive docs outside local development.
        docs_url="/api/docs" if settings.env == "local" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.env == "local" else None,
    )
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
            max_age=600,
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except OperationalError as exc:
            # Database unreachable or resuming from zero capacity: tell the client to retry.
            log.warning("http.db_unavailable", error_type=type(exc).__name__)
            response = JSONResponse({"error": "db_unavailable"}, status_code=503, headers={"Retry-After": "15"})
        except Exception as exc:
            # Handled here rather than by an exception handler so the response still gets the
            # security headers and request ID. Only the exception type is logged, never its message.
            log.error("http.unhandled", error_type=type(exc).__name__)
            response = JSONResponse({"error": "internal"}, status_code=500)
        route = request.scope.get("route")
        log.info(
            "http.request",
            method=request.method,
            # The route template (/api/admin/diagnostics/draft-probe/{draft_id}), never the raw path.
            route=getattr(route, "path", "unmatched"),
            status=response.status_code,
            duration_ms=round((time.perf_counter() - start) * 1000, 1),
        )
        response.headers.update(SECURITY_HEADERS)
        response.headers["X-Request-Id"] = request_id
        return response

    @app.exception_handler(AuthError)
    async def _auth_error(_: Request, exc: AuthError) -> JSONResponse:
        headers = {"WWW-Authenticate": f'Bearer error="{exc.code}"'} if exc.status == 401 else None
        return JSONResponse({"error": exc.code}, status_code=exc.status, headers=headers)

    @app.exception_handler(DraftError)
    async def _draft_error(_: Request, exc: DraftError) -> JSONResponse:
        return JSONResponse({"error": exc.code, **exc.extra}, status_code=exc.status)

    @app.exception_handler(GraphError)
    async def _graph_error(_: Request, exc: GraphError) -> JSONResponse:
        status = 403 if exc.status in (401, 403) else 502
        return JSONResponse(
            {"error": "graph_error", "graphStatus": exc.status, "graphCode": exc.code}, status_code=status
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, dict) else {"error": _code_for(exc.status_code)}
        return JSONResponse(detail, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Field locations only; FastAPI's default echoes the offending input back.
        fields = [".".join(str(p) for p in e.get("loc", ())) for e in exc.errors()]
        return JSONResponse({"error": "invalid_request", "fields": fields}, status_code=422)

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    async def readyz(request: Request) -> JSONResponse:
        try:
            async with request.app.state.vanimo.engine.connect() as conn:
                await conn.execute(text("select 1"))
        except Exception as exc:
            log.warning("readyz.db_unavailable", error_type=type(exc).__name__)
            return JSONResponse({"status": "db_unavailable"}, status_code=503)
        return JSONResponse({"status": "ready"})

    app.include_router(auth.router)
    app.include_router(me.router)
    app.include_router(controls.router)
    app.include_router(admin_scoping.router)
    app.include_router(diagnostics.router)
    app.include_router(learning.router)
    app.include_router(drafting.router)
    app.include_router(queue.router)
    app.include_router(edits.router)
    return app


def _code_for(status: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
    }.get(status, "error")


def __getattr__(name: str) -> FastAPI:
    # `uvicorn vanimo.main:app` builds the app lazily so importing this module has no side effects.
    if name == "app":
        return create_app()
    raise AttributeError(name)
