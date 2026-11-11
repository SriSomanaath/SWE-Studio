"""Ingest endpoint — accept .traj JSON from any source.

Designed so an external project (Aider, OpenHands, custom agent) can push
trajectories with a single HTTP POST. The file is written atomically into
`TRAJECTORIES_DIR/{run_id}/{trajectory_id}.traj`; watchfiles + the indexer
then pick it up the same way they would a local agent write.

The shape is permissive — fields outside the documented schema are kept.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError

from app import indexer, observability
from app.config import settings
from app.schemas import IngestResult, TrajectoryFile

router = APIRouter(tags=["ingest"])
logger = logging.getLogger(__name__)


def _mirror_to_s3(path: Path, run_id: str) -> None:
    """Copy an ingested file to s3://$TRAJECTORIES_BUCKET/<run_id>/<name>.

    The local file stays the source of truth (indexer, viewer and live mode
    read from disk); S3 is the durable copy that survives losing the cluster.
    An S3 failure is logged, not raised: the runner's data is already safe
    locally, and failing here would make it retry a run that succeeded.
    """
    if not settings.trajectories_bucket:
        return
    try:
        import boto3  # lazy: only needed when mirroring is on

        boto3.client("s3").upload_file(
            str(path), settings.trajectories_bucket, f"{run_id}/{path.name}"
        )
    except Exception:
        logger.exception("S3 mirror failed for %s/%s", run_id, path.name)


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
    try:
        parsed = TrajectoryFile.model_validate(payload.model_dump())
    except ValidationError as exc:  # the sender's fault: 422, not a 500
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False)) from exc

    root = settings.trajectories_dir.resolve()
    run_dir = (root / run_id).resolve()
    if root not in run_dir.parents and run_dir != root:
        raise HTTPException(status_code=400, detail="run_id resolves outside trajectories root")

    run_dir.mkdir(parents=True, exist_ok=True)
    dest = run_dir / f"{trajectory_id}.traj"
    # A re-post (e.g. the benchmark attaching ?eval= later) must not count the
    # run twice, so only the first write of a trajectory marks it finished.
    first_write = not dest.exists()
    tmp = dest.with_suffix(".traj.tmp")
    tmp.write_text(json.dumps(parsed.model_dump(), default=str))
    tmp.replace(dest)

    _mirror_to_s3(dest, run_id)
    info = payload.info
    if first_write:
        observability.run_finished(run_id, trajectory_id, info)
    if eval is not None:
        observability.metrics.inc(
            "agent_evals_total", model=str(info.get("model") or "unknown"), result=eval
        )
        _update_results(run_dir, trajectory_id, eval)
        _mirror_to_s3(run_dir / "results.json", run_id)

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


@router.post("/ingest/runs/{run_id}/trajectories/{trajectory_id}/eval", status_code=204)
def record_eval(
    run_id: str,
    trajectory_id: str,
    result: Annotated[Literal["resolved", "submitted", "failed", "completed"], Query()],
) -> None:
    """Attach an evaluation verdict to an already-ingested trajectory.

    Used by scripts/bench_swebench.py after the SWE-bench harness has run,
    so the verdict lands in results.json, the index and the pass-rate metric
    without re-uploading the trajectory.
    """
    run_id = _validate_id(run_id, "run_id")
    trajectory_id = _validate_id(trajectory_id, "trajectory_id")
    run_dir = (settings.trajectories_dir.resolve() / run_id).resolve()
    traj = run_dir / f"{trajectory_id}.traj"
    if not traj.exists():
        raise HTTPException(status_code=404, detail="trajectory not ingested")
    model = json.loads(traj.read_text()).get("info", {}).get("model") or "unknown"
    _update_results(run_dir, trajectory_id, result)
    _mirror_to_s3(run_dir / "results.json", run_id)
    observability.metrics.inc("agent_evals_total", model=str(model), result=result)
    indexer._reindex_run(run_dir)  # noqa: SLF001
