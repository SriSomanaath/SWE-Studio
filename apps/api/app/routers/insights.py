from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app import embeddings
from app import insights as svc
from app.schemas import EmbeddingsStatus, RunInsights, SimilarHit

router = APIRouter(tags=["insights"])


@router.get("/runs/{run_id}/insights", response_model=RunInsights)
def get_insights(run_id: str) -> RunInsights:
    return svc.run_insights(run_id)


@router.get(
    "/runs/{run_id}/trajectories/{trajectory_id}/similar",
    response_model=list[SimilarHit],
)
def get_similar(
    run_id: str,
    trajectory_id: str,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    mode: Annotated[Literal["auto", "semantic", "fts"], Query()] = "auto",
) -> list[SimilarHit]:
    return svc.find_similar(run_id, trajectory_id, limit, mode)


@router.get("/embeddings/status", response_model=EmbeddingsStatus)
def get_embeddings_status() -> EmbeddingsStatus:
    return EmbeddingsStatus(**embeddings.status_payload())
