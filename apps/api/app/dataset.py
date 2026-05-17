"""Dataset export — HuggingFace-Datasets-compatible JSONL + manifest.

The JSONL stream emits one self-contained record per trajectory. The schema is
stable and matches what an ML researcher would expect to consume:

    {
      "run_id": "sample-run-001",
      "instance_id": "django__django-12345",
      "problem_statement": "...",
      "exit_status": "submitted",
      "resolved": true,
      "submitted": true,
      "completed": true,
      "submission": "diff --git a/...",
      "step_count": 7,
      "instance_cost": 0.27,
      "tokens_sent": 18420,
      "tokens_received": 1923,
      "api_calls": 7,
      "steps": [{"thought": "...", "action": "...", "observation": "..."}, ...]
    }
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterator

from fastapi import HTTPException

from app import __version__, db
from app.trajectory_store import get_trajectory


def iter_jsonl(run_id: str) -> Iterator[bytes]:
    """Stream one record per `.traj` in this run."""
    if not db.fetch_one("SELECT 1 FROM runs WHERE id = ?", (run_id,)):
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    rows = db.fetch_all(
        "SELECT id FROM trajectories WHERE run_id = ? ORDER BY id ASC",
        (run_id,),
    )
    for r in rows:
        detail = get_trajectory(run_id, r["id"])
        record = _record_from_detail(detail)
        yield (json.dumps(record, separators=(",", ":")) + "\n").encode()


def _record_from_detail(detail: Any) -> dict[str, Any]:
    stats = detail.info.model_stats
    eval_status = detail.eval
    return {
        "run_id": detail.run_id,
        "instance_id": detail.id,
        "problem_statement": detail.problem_statement,
        "exit_status": detail.info.exit_status,
        "resolved": _b(eval_status.resolved),
        "submitted": _b(eval_status.submitted),
        "completed": _b(eval_status.completed),
        "submission": detail.info.submission,
        "step_count": len(detail.steps),
        "instance_cost": stats.instance_cost,
        "tokens_sent": stats.tokens_sent,
        "tokens_received": stats.tokens_received,
        "api_calls": stats.api_calls,
        "steps": [
            {
                "thought": s.thought,
                "action": s.action,
                "observation": s.observation,
                "response": s.response,
            }
            for s in detail.steps
        ],
    }


def _b(v: Any) -> bool | None:
    if v is None:
        return None
    return bool(v)


def manifest(run_id: str) -> dict[str, Any]:
    """Run-level metadata + per-instance stats + provenance."""
    if not db.fetch_one("SELECT 1 FROM runs WHERE id = ?", (run_id,)):
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    rows = db.fetch_all(
        """
        SELECT id, exit_status, instance_cost, step_count, api_calls,
               tokens_sent, tokens_received,
               eval_completed, eval_submitted, eval_resolved
        FROM trajectories
        WHERE run_id = ?
        ORDER BY id ASC
        """,
        (run_id,),
    )
    n = len(rows)
    resolved = sum(1 for r in rows if r["eval_resolved"] == 1)
    submitted = sum(1 for r in rows if r["eval_submitted"] == 1)
    total_cost = sum((r["instance_cost"] or 0.0) for r in rows)
    total_steps = sum((r["step_count"] or 0) for r in rows)

    return {
        "studio_version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "record_count": n,
        "format": "jsonl",
        "schema_version": 1,
        "stats": {
            "resolved_count": resolved,
            "submitted_count": submitted,
            "pass_rate": (resolved / n) if n else None,
            "total_cost_usd": round(total_cost, 4),
            "total_steps": total_steps,
        },
        "instances": [
            {
                "instance_id": r["id"],
                "exit_status": r["exit_status"],
                "resolved": _b(r["eval_resolved"]),
                "submitted": _b(r["eval_submitted"]),
                "step_count": r["step_count"] or 0,
                "instance_cost": r["instance_cost"],
                "tokens_sent": r["tokens_sent"],
                "tokens_received": r["tokens_received"],
                "api_calls": r["api_calls"],
            }
            for r in rows
        ],
        "schema_fields": [
            "run_id",
            "instance_id",
            "problem_statement",
            "exit_status",
            "resolved",
            "submitted",
            "completed",
            "submission",
            "step_count",
            "instance_cost",
            "tokens_sent",
            "tokens_received",
            "api_calls",
            "steps",
        ],
    }
