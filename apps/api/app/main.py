from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app import __version__, db, indexer
from app.auth import api_key_middleware
from app.config import settings
from app.observability import configure_logging, metrics
from app.routers import (
    agent as agent_router,
)
from app.routers import (
    dataset,
    export,
    ingest,
    insights,
    live,
    notes,
    presence,
    replay,
    runs,
    search,
    showcase,
    summary,
    webhooks,
)
from app.routers import (
    shares as shares_router,
)
from app.routers import (
    workspaces as workspaces_router,
)
from app.schemas import HealthResponse
from app.streaming import bus
from app.trajectory_store import root_diagnostics
from app.webhooks import delivery_worker

configure_logging("INFO")
logger = logging.getLogger(__name__)


def _refresh_gauges() -> None:
    try:
        traj_row = db.fetch_one("SELECT COUNT(*) AS n FROM trajectories")
        run_row = db.fetch_one("SELECT COUNT(*) AS n FROM runs")
        metrics.set_gauge("trajectories_indexed", float(traj_row["n"]) if traj_row else 0)
        metrics.set_gauge("runs_indexed", float(run_row["n"]) if run_row else 0)
    except Exception:
        logger.warning("failed to refresh metric gauges", exc_info=True)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    db.initialize()
    bus.bind_loop(asyncio.get_running_loop())
    await asyncio.to_thread(indexer.bulk_reindex)
    _refresh_gauges()
    watch_task: asyncio.Task[None] | None = None
    if settings.indexer_enabled:
        watch_task = asyncio.create_task(indexer.watch_loop(), name="indexer-watcher")
    webhook_task: asyncio.Task[None] | None = asyncio.create_task(
        delivery_worker(), name="webhook-worker"
    )
    try:
        yield
    finally:
        for task in (watch_task, webhook_task):
            if task is None:
                continue
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass


app = FastAPI(
    title="SWE Studio API",
    version=__version__,
    description=(
        "Read/write API for agent trajectories. "
        "Phase 8: production hardening + API-key auth + AI summaries."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=[
        "*",
        "X-Author",
        "X-API-Key",
        "X-Studio-User",
        "X-Studio-Name",
        "X-Studio-Email",
        "X-Studio-Workspace",
    ],
    expose_headers=["X-Total-Count"],
)


@app.middleware("http")
async def telemetry(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:
        elapsed = time.perf_counter() - start
        metrics.inc(
            "api_requests_total",
            method=request.method,
            route=_route(request),
            status="500",
        )
        metrics.observe("api_request_duration_seconds", elapsed, route=_route(request))
        logger.exception(
            "unhandled error",
            extra={"path": request.url.path, "method": request.method},
        )
        raise
    elapsed = time.perf_counter() - start
    metrics.inc(
        "api_requests_total",
        method=request.method,
        route=_route(request),
        status=str(status),
    )
    metrics.observe("api_request_duration_seconds", elapsed, route=_route(request))
    return response


def _route(request: Request) -> str:
    route = request.scope.get("route")
    if route and hasattr(route, "path"):
        return route.path  # type: ignore[attr-defined]
    return request.url.path


app.middleware("http")(api_key_middleware)


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    path, exists = root_diagnostics()
    return HealthResponse(trajectories_dir=path, trajectories_dir_exists=exists)


@app.get("/metrics", tags=["meta"], response_class=Response)
def get_metrics() -> Response:
    _refresh_gauges()
    return Response(
        content=metrics.render(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


app.include_router(runs.router)
app.include_router(live.router)
app.include_router(notes.router)
app.include_router(export.router)
app.include_router(ingest.router)
app.include_router(search.router)
app.include_router(showcase.router)
app.include_router(summary.router)
app.include_router(dataset.router)
app.include_router(insights.router)
app.include_router(webhooks.router)
app.include_router(shares_router.router)
app.include_router(workspaces_router.router)
app.include_router(presence.router)
app.include_router(replay.router)
app.include_router(agent_router.router)
