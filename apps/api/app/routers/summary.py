from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app import summarize as svc
from app.schemas import AISummary

router = APIRouter(tags=["summary"])


@router.post(
    "/runs/{run_id}/trajectories/{trajectory_id}/summarize",
    response_model=AISummary,
)
def post_summarize(
    run_id: str,
    trajectory_id: str,
    provider: Annotated[Literal["heuristic", "ai"], Query()] = "heuristic",
    force: Annotated[bool, Query(description="Bypass the cache and regenerate.")] = False,
) -> AISummary:
    return svc.summarize(run_id, trajectory_id, provider, force=force)


@router.get(
    "/runs/{run_id}/trajectories/{trajectory_id}/summary",
    response_model=AISummary | None,
)
def get_summary(
    run_id: str,
    trajectory_id: str,
    provider: Annotated[Literal["heuristic", "ai"], Query()] = "heuristic",
) -> AISummary | None:
    return svc._cache_get(run_id, trajectory_id, provider)  # type: ignore[attr-defined]


@router.get("/summary/status", tags=["summary"])
def get_summary_status() -> dict[str, bool]:
    """Tell the web app whether AI summaries are available in this deployment."""
    return {"heuristic_available": True, "ai_available": svc.is_ai_available()}
