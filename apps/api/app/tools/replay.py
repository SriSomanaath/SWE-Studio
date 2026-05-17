"""Replay a completed `.traj` into a destination path one step at a time.

Useful for demoing Live mode in SWE Studio without running a real agent.
The destination file is rewritten in place each step, which matches how the
real agent writes incremental trajectories.

Usage::

    python -m app.tools.replay \\
        --src ../../fixtures/trajectories/sample-run-001/django__django-12345.traj \\
        --dst /tmp/live-demo/django-12345/django__django-12345.traj \\
        --delay 2.0
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any


def _running_payload(raw: dict[str, Any], step_index: int) -> dict[str, Any]:
    steps = raw.get("trajectory") or []
    base_info = raw.get("info") or {}
    stats = base_info.get("model_stats") or {}
    total_steps = len(steps)

    # Linearly interpolate cost / tokens / api_calls so live stats grow over time.
    factor = (step_index + 1) / total_steps if total_steps else 0.0

    def scale(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return type(value)(value * factor)
        return value

    return {
        "history": raw.get("history") or [],
        "trajectory": steps[: step_index + 1],
        "info": {
            "exit_status": "running",
            "submission": None,
            "model_stats": {
                "instance_cost": scale(stats.get("instance_cost")),
                "tokens_sent": scale(stats.get("tokens_sent")),
                "tokens_received": scale(stats.get("tokens_received")),
                "api_calls": step_index + 1,
            },
        },
    }


def _atomic_write(dst: Path, payload: dict[str, Any]) -> None:
    """Write via temp file + rename so the indexer never sees a partial file."""
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    tmp.write_text(json.dumps(payload))
    tmp.replace(dst)


def replay(src: Path, dst: Path, delay: float = 2.0) -> int:
    raw = json.loads(src.read_text())
    steps = raw.get("trajectory") or []
    dst.parent.mkdir(parents=True, exist_ok=True)

    # Copy any results.json alongside the destination so the indexer can pick
    # up eval state once the run "finishes".
    src_results = src.parent / "results.json"
    if src_results.exists():
        shutil.copyfile(src_results, dst.parent / "results.json")

    # Start with an empty trajectory so subscribers see growth from 0.
    _atomic_write(dst, _running_payload(raw, step_index=-1))

    for i in range(len(steps)):
        time.sleep(delay)
        _atomic_write(dst, _running_payload(raw, step_index=i))
        print(f"step {i + 1}/{len(steps)}", flush=True)

    time.sleep(delay)
    _atomic_write(dst, raw)  # final write with original info
    print("done", flush=True)
    return len(steps)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", required=True, type=Path, help="Source .traj file")
    parser.add_argument("--dst", required=True, type=Path, help="Destination .traj file")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between steps")
    args = parser.parse_args(argv)

    if not args.src.exists():
        print(f"source not found: {args.src}", file=sys.stderr)
        return 1
    replay(args.src, args.dst, delay=args.delay)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
