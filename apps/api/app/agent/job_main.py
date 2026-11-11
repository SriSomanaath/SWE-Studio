"""Entrypoint for a Kubernetes agent Job (`python -m app.agent.job_main`).

Config comes from env (set by app.agent.k8s.build_job). The pod is the
sandbox, so the bash tool runs as a plain subprocess. The finished `.traj`
is POSTed to the API's existing /ingest endpoint; a non-zero exit marks the
Job failed so `GET /agent/runs/{id}/status` reports it.
"""

from __future__ import annotations

import logging
import os
import sys
import time
import urllib.request
from pathlib import Path

from app.agent.runner import AgentConfig, run_agent

logger = logging.getLogger("job_main")


def upload(url: str, body: bytes, api_key: str | None, attempts: int = 3) -> None:
    # Retry because backoffLimit=0: a transient API blip would otherwise
    # throw away a run we already paid the LLM for.
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                logger.info("ingested %s -> %s", url, resp.status)
                return
        except Exception:
            if i == attempts - 1:
                raise
            logger.warning("ingest attempt %d failed, retrying", i + 1, exc_info=True)
            time.sleep(2 ** i)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    env = os.environ
    run_id, traj_id = env["RUN_ID"], env["TRAJECTORY_ID"]
    config = AgentConfig(
        model=env["MODEL"],
        # None lets litellm pick the right provider key from env
        # (ANTHROPIC_API_KEY, OPENAI_API_KEY, ...) for whichever model runs.
        api_key=None,
        max_steps=int(env.get("MAX_STEPS", "30")),
        max_cost_usd=float(env.get("MAX_COST_USD", "5.0")),
        workdir=Path.cwd().resolve(),
        problem_statement=env.get("PROBLEM", ""),
    )
    result = run_agent(
        config, run_id=run_id, trajectory_id=traj_id, trajectories_dir=Path("/tmp/traj")
    )
    logger.info("run finished: %s, %d steps, $%.4f", result.exit_status, result.step_count, result.instance_cost)

    url = f"{env['INGEST_URL'].rstrip('/')}/ingest/runs/{run_id}/trajectories/{traj_id}"
    upload(url, result.file_path.read_bytes(), env.get("STUDIO_API_KEY"))
    return 0 if result.exit_status != "exit_error" else 1


if __name__ == "__main__":
    sys.exit(main())
