from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response

from app.schemas import (
    RunAnalytics,
    RunCompareResult,
    RunStats,
    RunSummary,
    TrajectoryDetail,
    TrajectorySummary,
)
from app.trajectory_store import (
    SortField,
    SortOrder,
    StatusFilter,
    compare_runs,
    get_trajectory,
    list_runs,
    list_trajectories,
    run_analytics,
    run_stats,
)

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=list[RunSummary])
def get_runs() -> list[RunSummary]:
    return list_runs()


StatusQuery = Annotated[
    Literal["any", "resolved", "submitted", "failed", "unscored"],
    Query(description="Filter by evaluation status."),
]
SortQuery = Annotated[
    Literal["id", "instance_cost", "api_calls", "step_count", "tokens_sent"],
    Query(),
]
OrderQuery = Annotated[Literal["asc", "desc"], Query()]


@router.get("/{run_id}/trajectories", response_model=list[TrajectorySummary])
def get_trajectories(
    run_id: str,
    response: Response,
    status: StatusQuery = "any",
    exit: Annotated[str | None, Query(max_length=128)] = None,
    search: Annotated[str | None, Query(max_length=256)] = None,
    cost_min: Annotated[float | None, Query(ge=0)] = None,
    cost_max: Annotated[float | None, Query(ge=0)] = None,
    sort: SortQuery = "id",
    order: OrderQuery = "asc",
    limit: Annotated[int, Query(ge=1, le=10000)] = 1000,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TrajectorySummary]:
    rows, total = list_trajectories(
        run_id,
        status_filter=status,  # type: ignore[arg-type]
        exit_substring=exit,
        search=search,
        cost_min=cost_min,
        cost_max=cost_max,
        sort=sort,  # type: ignore[arg-type]
        order=order,  # type: ignore[arg-type]
        limit=limit,
        offset=offset,
    )
    response.headers["X-Total-Count"] = str(total)
    return rows


@router.get("/{run_id}/stats", response_model=RunStats)
def get_run_stats(run_id: str) -> RunStats:
    return run_stats(run_id)


@router.get("/{run_id}/analytics", response_model=RunAnalytics)
def get_run_analytics(run_id: str) -> RunAnalytics:
    return run_analytics(run_id)


@router.get("/compare", response_model=RunCompareResult, tags=["compare"])
def get_runs_compare(a: str, b: str) -> RunCompareResult:
    return compare_runs(a, b)


@router.get(
    "/{run_id}/trajectories/{trajectory_id}",
    response_model=TrajectoryDetail,
)
def get_trajectory_detail(run_id: str, trajectory_id: str) -> TrajectoryDetail:
    return get_trajectory(run_id, trajectory_id)
