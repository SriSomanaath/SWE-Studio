from __future__ import annotations

import json
from typing import Annotated, AsyncIterator

from fastapi import APIRouter, Query, Request
from sse_starlette.sse import EventSourceResponse

from app.schemas import CompareResult, LiveTrajectory
from app.streaming import bus, channel_run, channel_traj
from app.trajectory_store import compare, list_live

router = APIRouter(tags=["live"])


@router.get("/live", response_model=list[LiveTrajectory])
def get_live(
    since: Annotated[float, Query(ge=1, le=3600)] = 60,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[LiveTrajectory]:
    """Trajectories modified in the last `since` seconds."""
    return list_live(since_seconds=since, limit=limit)


@router.get("/runs/{run_id}/trajectories/{trajectory_id}/events")
async def stream_trajectory_events(run_id: str, trajectory_id: str, request: Request):
    return EventSourceResponse(
        _stream(request, channel_traj(run_id, trajectory_id)),
        ping=15,
    )


@router.get("/runs/{run_id}/events")
async def stream_run_events(run_id: str, request: Request):
    return EventSourceResponse(_stream(request, channel_run(run_id)), ping=15)


async def _stream(request: Request, channel: str) -> AsyncIterator[dict[str, str]]:
    async for event in bus.stream(channel):
        if await request.is_disconnected():
            break
        yield {"event": event.get("type", "message"), "data": json.dumps(event)}


@router.get("/compare", response_model=CompareResult)
def get_compare(
    a: Annotated[str, Query(description="run_id:trajectory_id")],
    b: Annotated[str, Query(description="run_id:trajectory_id")],
) -> CompareResult:
    return compare(a, b)
