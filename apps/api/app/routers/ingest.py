"""Ingest endpoint — accept .traj JSON from any source.

Designed so an external project (Aider, OpenHands, custom agent) can push
trajectories with a single HTTP POST. The file is written atomically into
`TRAJECTORIES_DIR/{run_id}/{trajectory_id}.traj`; watchfiles + the indexer
then pick it up the same way they would a local agent write.

The shape is permissive — fields outside the documented schema are kept.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app import indexer
from app.config import settings
from app.schemas import IngestResult, TrajectoryFile

router = APIRouter(tags=["ingest"])


_ID_RE = re.compile(r"^[A-Za-z0-9._\-]+$")


def _validate_id(name: str, kind: str) -> str:
    if not _ID_RE.match(name):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{kind} must match [A-Za-z0-9._-]+; refused '{name}' to keep the "
                "trajectories directory safe."
            ),
        )
    return name


class IngestPayload(BaseModel):
    """A trajectory.

    Outside-of-spec extras under `info` or `trajectory[*]` are preserved.
    """

    history: list[dict[str, Any]] = Field(default_factory=list)
    trajectory: list[dict[str, Any]] = Field(default_factory=list)
    info: dict[str, Any] = Field(default_factory=dict)


@router.post(
    "/ingest/runs/{run_id}/trajectories/{trajectory_id}",
    response_model=IngestResult,
    status_code=201,
)
def ingest_trajectory(
    run_id: str,
    trajectory_id: str,
    payload: IngestPayload,
    eval: Annotated[
        Literal["resolved", "submitted", "failed", "completed"] | None,
        Query(description="Optional eval status to record alongside the trajectory."),
    ] = None,
) -> IngestResult:
    run_id = _validate_id(run_id, "run_id")
    trajectory_id = _validate_id(trajectory_id, "trajectory_id")

    # Round-trip through TrajectoryFile so we share validation with the reader.
    parsed = TrajectoryFile.model_validate(payload.model_dump())

    root = settings.trajectories_dir.resolve()
    run_dir = (root / run_id).resolve()
    if root not in run_dir.parents and run_dir != root:
        raise HTTPException(status_code=400, detail="run_id resolves outside trajectories root")

    run_dir.mkdir(parents=True, exist_ok=True)
    dest = run_dir / f"{trajectory_id}.traj"
    tmp = dest.with_suffix(".traj.tmp")
    tmp.write_text(json.dumps(parsed.model_dump(), default=str))
    tmp.replace(dest)

    if eval is not None:
        _update_results(run_dir, trajectory_id, eval)

    # Synchronously reindex so callers see their write reflected immediately,
    # even if watchfiles hasn't fired yet (e.g., in CI / Docker mounts).
    indexer._reindex_run(run_dir)  # noqa: SLF001

    return IngestResult(
        run_id=run_id,
        trajectory_id=trajectory_id,
        file_path=str(dest),
    )


def _update_results(run_dir: Path, trajectory_id: str, eval_status: str) -> None:
    results_path = run_dir / "results.json"
    if results_path.exists():
        try:
            data = json.loads(results_path.read_text())
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    for key in ("completed_ids", "submitted_ids", "resolved_ids"):
        data.setdefault(key, [])

    def _ensure(key: str) -> None:
        if trajectory_id not in data[key]:
            data[key].append(trajectory_id)

    _ensure("completed_ids")
    if eval_status == "submitted":
        _ensure("submitted_ids")
    elif eval_status == "resolved":
        _ensure("submitted_ids")
        _ensure("resolved_ids")
    elif eval_status == "failed":
        # remove from resolved if present
        data["resolved_ids"] = [t for t in data["resolved_ids"] if t != trajectory_id]

    tmp = results_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(results_path)
