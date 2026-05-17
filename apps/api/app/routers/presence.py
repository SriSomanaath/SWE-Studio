from __future__ import annotations

import json
from typing import Annotated, AsyncIterator

from fastapi import APIRouter, Header, Query, Request
from sse_starlette.sse import EventSourceResponse

from app import presence as svc
from app.schemas import PresenceState
from app.streaming import bus

router = APIRouter(prefix="/runs", tags=["presence"])

UserHeader = Annotated[str | None, Header(alias="X-Studio-User")]
NameHeader = Annotated[str | None, Header(alias="X-Studio-Name")]


@router.post(
    "/{run_id}/trajectories/{trajectory_id}/presence",
    response_model=PresenceState,
)
def post_presence(
    run_id: str,
    trajectory_id: str,
    step: Annotated[int | None, Query()] = None,
    user_id: Annotated[str | None, Query()] = None,
    x_studio_user: UserHeader = None,
    x_studio_name: NameHeader = None,
) -> PresenceState:
    uid = user_id or x_studio_user or "anonymous"
    return svc.upsert(run_id, trajectory_id, uid, x_studio_name, step)


@router.delete(
    "/{run_id}/trajectories/{trajectory_id}/presence",
    response_model=PresenceState,
)
def delete_presence(
    run_id: str,
    trajectory_id: str,
    user_id: Annotated[str | None, Query()] = None,
    x_studio_user: UserHeader = None,
) -> PresenceState:
    uid = user_id or x_studio_user or "anonymous"
    return svc.remove(run_id, trajectory_id, uid)


@router.get(
    "/{run_id}/trajectories/{trajectory_id}/presence",
    response_model=PresenceState,
)
def get_presence(run_id: str, trajectory_id: str) -> PresenceState:
    return svc.snapshot(run_id, trajectory_id)


@router.get("/{run_id}/trajectories/{trajectory_id}/presence/stream")
async def stream_presence(run_id: str, trajectory_id: str, request: Request):
    """SSE stream of presence events for this trajectory."""
    initial = svc.snapshot(run_id, trajectory_id)

    async def gen() -> AsyncIterator[dict[str, str]]:
        # Bootstrap subscriber with the current viewers.
        yield {
            "event": "presence",
            "data": json.dumps({"type": "presence", **initial.model_dump()}),
        }
        async for event in bus.stream(svc.channel(run_id, trajectory_id)):
            if await request.is_disconnected():
                break
            yield {"event": "presence", "data": json.dumps(event)}

    return EventSourceResponse(gen(), ping=15)
