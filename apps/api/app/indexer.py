"""Filesystem-to-SQLite indexer.

Two entry points:

* `bulk_reindex()` — full scan, called on startup.
* `watch_loop()` — long-running async task that reacts to filesystem events.

The indexer is intentionally conservative: any parse error on a single file is
swallowed so one bad `.traj` cannot poison the whole index. The next valid
event for that file (e.g., the agent finishing its atomic write) will retry.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from watchfiles import Change, awatch

from app import db, embeddings
from app.config import settings
from app.streaming import bus, channel_run, channel_traj

logger = logging.getLogger(__name__)


# Most recently seen state, used to emit deltas when a .traj is rewritten.
_last_state: dict[tuple[str, str], dict[str, Any]] = {}
# Set to True during the initial scan so we don't emit a flood of "new traj"
# events on startup.
_emitting = False


def _root() -> Path:
    return settings.trajectories_dir.resolve()


def _safe_load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        logger.debug("Skipping unreadable file %s: %s", path, exc)
        return None


def _extract_problem_statement(traj: dict[str, Any]) -> str | None:
    for msg in traj.get("history", []) or []:
        if msg.get("role") == "user" and msg.get("content"):
            content = msg["content"]
            return content if len(content) < 4000 else content[:4000]
    return None


def _eval_for(instance_id: str, results: dict[str, Any] | None) -> tuple[bool | None, ...]:
    if not results:
        return (None, None, None)
    return (
        instance_id in results.get("completed_ids", []),
        instance_id in results.get("submitted_ids", []),
        instance_id in results.get("resolved_ids", []),
    )


def _step_text(raw: dict[str, Any]) -> str:
    """Flatten step thoughts/actions/observations into a single FTS5-friendly blob."""
    parts: list[str] = []
    for step in raw.get("trajectory") or []:
        for key in ("thought", "action", "observation"):
            value = step.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value)
    return "\n".join(parts)[:200_000]  # FTS5 happily handles this; cap for safety.


def _index_traj_file(
    run_id: str, run_dir: Path, traj_path: Path, results: dict[str, Any] | None
) -> None:
    raw = _safe_load_json(traj_path)
    if raw is None:
        return

    info = raw.get("info") or {}
    stats = info.get("model_stats") or {}
    instance_id = traj_path.stem
    completed, submitted, resolved = _eval_for(instance_id, results)
    step_count = len(raw.get("trajectory") or [])
    problem = _extract_problem_statement(raw) or ""
    step_text = _step_text(raw)

    row = {
        "run_id": run_id,
        "id": instance_id,
        "file_path": str(traj_path.resolve()),
        "relative_path": str(traj_path.relative_to(run_dir)),
        "mtime": traj_path.stat().st_mtime,
        "exit_status": info.get("exit_status"),
        "api_calls": stats.get("api_calls"),
        "instance_cost": stats.get("instance_cost"),
        "tokens_sent": stats.get("tokens_sent"),
        "tokens_received": stats.get("tokens_received"),
        "step_count": step_count,
        "eval_completed": _bool_to_int(completed),
        "eval_submitted": _bool_to_int(submitted),
        "eval_resolved": _bool_to_int(resolved),
        "problem_statement": _extract_problem_statement(raw),
    }

    with db.write_tx() as conn:
        conn.execute(
            """
            INSERT INTO trajectories (
                run_id, id, file_path, relative_path, mtime,
                exit_status, api_calls, instance_cost, tokens_sent, tokens_received, step_count,
                eval_completed, eval_submitted, eval_resolved, problem_statement
            )
            VALUES (
                :run_id, :id, :file_path, :relative_path, :mtime,
                :exit_status, :api_calls, :instance_cost, :tokens_sent, :tokens_received, :step_count,
                :eval_completed, :eval_submitted, :eval_resolved, :problem_statement
            )
            ON CONFLICT(run_id, id) DO UPDATE SET
                file_path       = excluded.file_path,
                relative_path   = excluded.relative_path,
                mtime           = excluded.mtime,
                exit_status     = excluded.exit_status,
                api_calls       = excluded.api_calls,
                instance_cost   = excluded.instance_cost,
                tokens_sent     = excluded.tokens_sent,
                tokens_received = excluded.tokens_received,
                step_count      = excluded.step_count,
                eval_completed  = excluded.eval_completed,
                eval_submitted  = excluded.eval_submitted,
                eval_resolved   = excluded.eval_resolved,
                problem_statement = excluded.problem_statement
            """,
            row,
        )

        # Keep FTS in sync. FTS5 contentless tables don't support upsert, so
        # delete-then-insert is the standard pattern.
        conn.execute(
            "DELETE FROM trajectories_fts WHERE run_id = ? AND trajectory_id = ?",
            (run_id, instance_id),
        )
        conn.execute(
            """
            INSERT INTO trajectories_fts (run_id, trajectory_id, instance_id, problem, step_text)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, instance_id, instance_id, problem, step_text),
        )

    # Embeddings live outside the SQL transaction because encoding may be slow
    # (CPU-bound) and we don't want to hold the write lock during inference.
    try:
        embeddings.upsert_for_trajectory(
            run_id, instance_id, problem=problem, action_text=step_text
        )
    except Exception:
        logger.exception("embedding upsert failed for %s:%s", run_id, instance_id)

    _maybe_emit(run_id, instance_id, row, step_count)


def _maybe_emit(run_id: str, instance_id: str, row: dict[str, Any], step_count: int) -> None:
    if not _emitting:
        _last_state[(run_id, instance_id)] = {
            "step_count": step_count,
            "exit_status": row["exit_status"],
            "eval_resolved": row["eval_resolved"],
        }
        return

    prev = _last_state.get((run_id, instance_id))
    current = {
        "step_count": step_count,
        "exit_status": row["exit_status"],
        "eval_resolved": row["eval_resolved"],
    }
    _last_state[(run_id, instance_id)] = current

    if prev is None:
        bus.publish(
            channel_traj(run_id, instance_id),
            {
                "type": "new",
                "run_id": run_id,
                "trajectory_id": instance_id,
                "step_count": step_count,
                "exit_status": row["exit_status"],
                "eval_resolved": bool(row["eval_resolved"])
                if row["eval_resolved"] is not None
                else None,
            },
        )
        bus.publish(
            channel_run(run_id),
            {"type": "trajectory_added", "run_id": run_id, "trajectory_id": instance_id},
        )
        return

    if prev == current:
        return

    bus.publish(
        channel_traj(run_id, instance_id),
        {
            "type": "update",
            "run_id": run_id,
            "trajectory_id": instance_id,
            "step_count": step_count,
            "step_count_delta": step_count - prev["step_count"],
            "exit_status": row["exit_status"],
            "exit_status_changed": prev["exit_status"] != row["exit_status"],
            "eval_resolved": bool(row["eval_resolved"])
            if row["eval_resolved"] is not None
            else None,
        },
    )
    bus.publish(
        channel_run(run_id),
        {"type": "trajectory_updated", "run_id": run_id, "trajectory_id": instance_id},
    )


def _bool_to_int(v: bool | None) -> int | None:
    return None if v is None else (1 if v else 0)


def _upsert_run(run_dir: Path, has_results: bool) -> None:
    root = _root()
    with db.write_tx() as conn:
        conn.execute(
            """
            INSERT INTO runs (id, relative_path, has_results, indexed_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                relative_path = excluded.relative_path,
                has_results   = excluded.has_results,
                indexed_at    = excluded.indexed_at
            """,
            (
                run_dir.name,
                str(run_dir.relative_to(root)),
                1 if has_results else 0,
                time.time(),
            ),
        )


def _reindex_run(run_dir: Path) -> None:
    if not run_dir.is_dir():
        return
    results_path = run_dir / "results.json"
    results = _safe_load_json(results_path) if results_path.exists() else None
    if results and "no_generation" in results and "not_generated" not in results:
        results["not_generated"] = results["no_generation"]

    _upsert_run(run_dir, has_results=results is not None)

    traj_files = list(run_dir.glob("**/*.traj"))
    existing_ids = {p.stem for p in traj_files}

    # Drop trajectories that have disappeared from disk.
    with db.write_tx() as conn:
        rows = conn.execute(
            "SELECT id FROM trajectories WHERE run_id = ?", (run_dir.name,)
        ).fetchall()
        stale = {r["id"] for r in rows} - existing_ids
        if stale:
            params = [(run_dir.name, sid) for sid in stale]
            conn.executemany("DELETE FROM trajectories WHERE run_id = ? AND id = ?", params)
            conn.executemany(
                "DELETE FROM trajectories_fts WHERE run_id = ? AND trajectory_id = ?",
                params,
            )

    for traj_path in traj_files:
        _index_traj_file(run_dir.name, run_dir, traj_path, results)


def bulk_reindex() -> None:
    """Full scan of `trajectories_dir`. Idempotent."""
    root = _root()
    if not root.exists():
        logger.warning("trajectories_dir does not exist: %s", root)
        return

    discovered_runs: set[str] = set()
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        traj_files = list(entry.glob("**/*.traj"))
        if not traj_files:
            continue
        discovered_runs.add(entry.name)
        _reindex_run(entry)

    # Drop runs that have disappeared.
    with db.write_tx() as conn:
        rows = conn.execute("SELECT id FROM runs").fetchall()
        stale = {r["id"] for r in rows} - discovered_runs
        if stale:
            conn.executemany("DELETE FROM runs WHERE id = ?", [(rid,) for rid in stale])


def _affected_runs(paths: list[str]) -> set[Path]:
    """Map each changed path to the run directory immediately under root."""
    root = _root()
    out: set[Path] = set()
    for p in paths:
        try:
            rel = Path(p).resolve().relative_to(root)
        except ValueError:
            continue
        if not rel.parts:
            continue
        out.add(root / rel.parts[0])
    return out


async def watch_loop() -> None:
    """Long-running watcher. Cancel the task to stop it."""
    global _emitting
    root = _root()
    if not root.exists():
        logger.warning("Indexer not starting — trajectories_dir missing: %s", root)
        return

    _emitting = True
    logger.info("Indexer watching %s", root)
    try:
        async for changes in awatch(str(root), recursive=True):
            relevant: list[str] = []
            for change_type, path in changes:
                if (
                    path.endswith(".traj")
                    or path.endswith("results.json")
                    or change_type == Change.deleted
                ):
                    relevant.append(path)
            if not relevant:
                continue
            for run_dir in _affected_runs(relevant):
                try:
                    _reindex_run(run_dir)
                except Exception:
                    logger.exception("Failed to reindex run %s", run_dir)
    except asyncio.CancelledError:
        logger.info("Indexer watch loop cancelled")
        raise
