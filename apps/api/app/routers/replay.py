"""Replay-into-sandbox endpoint.

Triggers Phase 3's `app.tools.replay` against an existing trajectory's source
file, writing into a fresh run directory under the configured trajectories
root. Watchfiles + the indexer pick the writes up, so the existing live-mode
SSE stream renders the playback in real time.

This is a "sandbox lite": no Docker, no fresh repo checkout — just a
filesystem-level re-emission of the saved steps. It's enough to validate the
replay UX end-to-end without committing to a full container runtime.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app import db
from app.config import settings
from app.schemas import ReplayResult
from app.tools import replay as replay_tool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/runs", tags=["replay"])


@router.post(
    "/{run_id}/trajectories/{trajectory_id}/replay",
    response_model=ReplayResult,
    status_code=202,
)
def post_replay(
    run_id: str,
    trajectory_id: str,
    delay: Annotated[float, Query(ge=0.1, le=10.0)] = 1.5,
) -> ReplayResult:
    src_row = db.fetch_one(
        "SELECT file_path, step_count FROM trajectories WHERE run_id = ? AND id = ?",
        (run_id, trajectory_id),
    )
    if not src_row:
        raise HTTPException(
            status_code=404,
            detail=f"Trajectory '{trajectory_id}' not found in run '{run_id}'",
        )

    src = Path(src_row["file_path"])
    if not src.exists():
        raise HTTPException(status_code=410, detail="Source .traj file has gone missing")

    timestamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    new_run_id = f"replay-{run_id}-{timestamp}"
    new_run_dir = (settings.trajectories_dir / new_run_id).resolve()
    new_run_dir.mkdir(parents=True, exist_ok=True)
    dst = new_run_dir / f"{trajectory_id}.traj"

    def _worker() -> None:
        try:
            replay_tool.replay(src, dst, delay=float(delay))
        except Exception:
            logger.exception("replay worker crashed for %s/%s", run_id, trajectory_id)

    thread = threading.Thread(target=_worker, daemon=True, name=f"replay-{new_run_id}")
    thread.start()

    events_url = f"/runs/{new_run_id}/trajectories/{trajectory_id}/events"
    return ReplayResult(
        new_run_id=new_run_id,
        trajectory_id=trajectory_id,
        events_url=events_url,
        step_count=int(src_row["step_count"] or 0),
    )
