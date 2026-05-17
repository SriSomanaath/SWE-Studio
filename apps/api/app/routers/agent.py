from __future__ import annotations

import logging
import os
import re
import threading
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.agent import AgentConfig, run_agent
from app.config import settings
from app.schemas import (
    AgentEnsembleAccepted,
    AgentEnsembleRequest,
    AgentRunAccepted,
    AgentRunRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _generate_ids(req: AgentRunRequest) -> tuple[str, str]:
    timestamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    run_id = req.run_id or f"agent-{timestamp}"
    trajectory_id = req.trajectory_id or f"instance-{timestamp}"
    if not _ID_RE.match(run_id):
        raise HTTPException(status_code=400, detail="run_id must match [A-Za-z0-9._-]+")
    if not _ID_RE.match(trajectory_id):
        raise HTTPException(status_code=400, detail="trajectory_id must match [A-Za-z0-9._-]+")
    return run_id, trajectory_id


@router.post("/run", response_model=AgentRunAccepted, status_code=202)
def post_run(req: AgentRunRequest) -> AgentRunAccepted:
    repo = Path(req.repo).resolve()
    if not repo.exists() or not repo.is_dir():
        raise HTTPException(status_code=400, detail=f"repo path not a directory: {req.repo}")

    run_id, trajectory_id = _generate_ids(req)
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")

    config = AgentConfig(
        model=req.model,
        api_key=api_key,
        max_steps=req.max_steps,
        max_cost_usd=req.max_cost_usd,
        workdir=repo,
        problem_statement=req.problem,
    )

    def _worker() -> None:
        try:
            run_agent(
                config,
                run_id=run_id,
                trajectory_id=trajectory_id,
                trajectories_dir=settings.trajectories_dir.resolve(),
            )
        except Exception:
            logger.exception("agent worker crashed for %s/%s", run_id, trajectory_id)

    threading.Thread(target=_worker, daemon=True, name=f"agent-{run_id}").start()

    file_path = (
        settings.trajectories_dir.resolve() / run_id / f"{trajectory_id}.traj"
    )
    return AgentRunAccepted(
        run_id=run_id,
        trajectory_id=trajectory_id,
        file_path=str(file_path),
        events_url=f"/runs/{run_id}/trajectories/{trajectory_id}/events",
        trajectory_url=f"/runs/{run_id}/{trajectory_id}",
    )


@router.post("/ensemble", response_model=AgentEnsembleAccepted, status_code=202)
def post_ensemble(req: AgentEnsembleRequest) -> AgentEnsembleAccepted:
    if len(req.models) < 1:
        raise HTTPException(status_code=400, detail="ensemble requires at least one model")
    if len(req.models) > 6:
        raise HTTPException(status_code=400, detail="ensemble capped at 6 models per call")

    repo = Path(req.repo).resolve()
    if not repo.exists() or not repo.is_dir():
        raise HTTPException(status_code=400, detail=f"repo path not a directory: {req.repo}")

    timestamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    run_id = f"ensemble-{timestamp}"
    if not _ID_RE.match(run_id):
        raise HTTPException(status_code=500, detail="generated run_id is not URL-safe")

    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")
    trajectories: list[AgentRunAccepted] = []
    for model in req.models:
        slug = model.replace("/", "_").replace(":", "_")
        trajectory_id = f"{slug}-{timestamp}"
        if not _ID_RE.match(trajectory_id):
            raise HTTPException(status_code=400, detail=f"model produced unsafe trajectory id: {model}")

        config = AgentConfig(
            model=model,
            api_key=api_key,
            max_steps=req.max_steps,
            max_cost_usd=req.max_cost_usd,
            workdir=repo,
            problem_statement=req.problem,
            docker_image=req.docker_image,
        )

        def _worker(_config: AgentConfig = config, _traj_id: str = trajectory_id) -> None:
            try:
                run_agent(
                    _config,
                    run_id=run_id,
                    trajectory_id=_traj_id,
                    trajectories_dir=settings.trajectories_dir.resolve(),
                )
            except Exception:
                logger.exception("ensemble worker crashed for %s/%s", run_id, _traj_id)

        threading.Thread(
            target=_worker, daemon=True, name=f"agent-{run_id}-{trajectory_id}"
        ).start()

        file_path = settings.trajectories_dir.resolve() / run_id / f"{trajectory_id}.traj"
        trajectories.append(
            AgentRunAccepted(
                run_id=run_id,
                trajectory_id=trajectory_id,
                file_path=str(file_path),
                events_url=f"/runs/{run_id}/trajectories/{trajectory_id}/events",
                trajectory_url=f"/runs/{run_id}/{trajectory_id}",
            )
        )

    # When 2 models race, the natural follow-up is the run-vs-run matrix.
    compare_url: str | None = None
    if len(req.models) >= 2:
        compare_url = f"/runs/{run_id}"  # all ensemble trajectories share one run

    return AgentEnsembleAccepted(
        run_id=run_id,
        trajectories=trajectories,
        compare_url=compare_url,
    )
