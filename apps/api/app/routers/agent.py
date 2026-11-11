from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app import observability
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


def _source(req: AgentRunRequest | AgentEnsembleRequest) -> Path | None:
    """Validate where the code comes from for the active executor."""
    if settings.agent_executor == "k8s":
        # https only: blocks file:// (reads the runner image) and ssh/git://.
        if not (req.repo_url or "").startswith("https://"):
            raise HTTPException(status_code=400, detail="k8s executor needs an https:// repo_url")
        return None
    repo = Path(req.repo).resolve()
    if not req.repo or not repo.is_dir():
        raise HTTPException(status_code=400, detail=f"repo path not a directory: {req.repo}")
    return repo


def _ensure_capacity(n: int) -> None:
    if settings.agent_executor != "k8s":
        return
    from app.agent import k8s

    try:
        k8s.ensure_capacity(n)
    except k8s.CapacityError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc


def _launch(
    config: AgentConfig,
    req: AgentRunRequest | AgentEnsembleRequest,
    run_id: str,
    trajectory_id: str,
) -> None:
    if settings.agent_executor == "k8s":
        from app.agent import k8s

        try:
            k8s.create_job(
                run_id=run_id,
                trajectory_id=trajectory_id,
                model=config.model,
                problem=config.problem_statement,
                repo_url=req.repo_url,
                repo_ref=req.repo_ref,
                max_steps=config.max_steps,
                max_cost_usd=config.max_cost_usd,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        observability.run_started(run_id, trajectory_id, config.model, "k8s")
        return

    observability.run_started(run_id, trajectory_id, config.model, "thread")

    def _worker() -> None:
        info: dict = {"model": config.model, "exit_status": "exit_crash"}
        try:
            result = run_agent(
                config,
                run_id=run_id,
                trajectory_id=trajectory_id,
                trajectories_dir=settings.trajectories_dir.resolve(),
            )
            info = json.loads(result.file_path.read_text())["info"]
        except Exception:
            logger.exception("agent worker crashed for %s/%s", run_id, trajectory_id)
        observability.run_finished(run_id, trajectory_id, info)

    threading.Thread(target=_worker, daemon=True, name=f"agent-{run_id}-{trajectory_id}").start()


@router.post("/run", response_model=AgentRunAccepted, status_code=202)
def post_run(req: AgentRunRequest) -> AgentRunAccepted:
    repo = _source(req)
    _ensure_capacity(1)
    run_id, trajectory_id = _generate_ids(req)
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")

    config = AgentConfig(
        model=req.model,
        api_key=api_key,
        max_steps=req.max_steps,
        max_cost_usd=req.max_cost_usd,
        workdir=repo or Path("."),
        problem_statement=req.problem,
    )
    _launch(config, req, run_id, trajectory_id)

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

    repo = _source(req)
    _ensure_capacity(len(req.models))  # all-or-nothing for a race
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
            workdir=repo or Path("."),
            problem_statement=req.problem,
            # Ignored by the k8s executor: the Job pod is already the sandbox.
            docker_image=req.docker_image,
        )
        # One Job per model; they're scheduled and run in parallel.
        _launch(config, req, run_id, trajectory_id)

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


@router.get("/runs/{run_id}/status")
def get_run_status(run_id: str) -> dict:
    """Per-trajectory {phase: pending|running|succeeded|failed, seconds} (k8s only)."""
    if settings.agent_executor != "k8s":
        raise HTTPException(status_code=400, detail="status needs AGENT_EXECUTOR=k8s")
    if not _ID_RE.match(run_id):
        raise HTTPException(status_code=400, detail="run_id must match [A-Za-z0-9._-]+")
    from app.agent import k8s

    trajectories = k8s.run_status(run_id)
    if not trajectories:
        raise HTTPException(status_code=404, detail=f"no jobs for run {run_id}")
    return {"run_id": run_id, "trajectories": trajectories}
