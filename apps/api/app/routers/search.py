from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app import search as search_svc
from app.schemas import SearchResult

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResult)
def get_search(
    q: Annotated[str, Query(min_length=1, max_length=256)],
    run_id: Annotated[str | None, Query()] = None,
    kind: Annotated[Literal["all", "trajectory", "annotation"], Query()] = "all",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> SearchResult:
    return search_svc.search(q, run_id=run_id, kind=kind, limit=limit)
