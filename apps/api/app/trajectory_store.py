"""Service layer over the SQLite index and the raw `.traj` files.

List/filter/stats queries go through SQLite. Trajectory detail still reads the
raw `.traj` file — we never duplicate step content into the database.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException, status

from app import db
from app.config import settings
from app import diff as diff_mod
from app.schemas import (
    BucketPassRate,
    CompareResult,
    CompareSummary,
    DiffAnalysis,
    DiffFileStat,
    EvalStatus,
    ExitStatusBreakdown,
    HistogramBin,
    InstanceCompareRow,
    InstanceSide,
    LiveTrajectory,
    RunAnalytics,
    RunCompareResult,
    RunCompareSummary,
    RunStats,
    RunSummary,
    TopTrajectory,
    TrajectoryDetail,
    TrajectoryFile,
    TrajectorySummary,
)

StatusFilter = Literal["any", "resolved", "submitted", "failed", "unscored"]
SortField = Literal["id", "instance_cost", "api_calls", "step_count", "tokens_sent"]
SortOrder = Literal["asc", "desc"]


def _root() -> Path:
    return settings.trajectories_dir.resolve()


def _safe_join(base: Path, *parts: str) -> Path:
    candidate = (base / Path(*parts)).resolve()
    if base not in candidate.parents and candidate != base:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path escapes trajectories root",
        )
    return candidate


def _load_traj_file(path: Path) -> TrajectoryFile:
    try:
        raw = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Trajectory not found") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=422, detail=f"Trajectory is not valid JSON: {exc}"
        ) from exc
    return TrajectoryFile.model_validate(raw)


def _eval_from_row(row: Any) -> EvalStatus:
    def b(v: int | None) -> bool | None:
        return None if v is None else bool(v)

    return EvalStatus(
        completed=b(row["eval_completed"]),
        submitted=b(row["eval_submitted"]),
        resolved=b(row["eval_resolved"]),
    )


def list_runs() -> list[RunSummary]:
    rows = db.fetch_all(
        """
        SELECT
            r.id,
            r.relative_path,
            r.has_results,
            COUNT(t.id)                                            AS trajectory_count,
            SUM(CASE WHEN t.eval_resolved  = 1 THEN 1 ELSE 0 END)  AS resolved_count,
            SUM(CASE WHEN t.eval_submitted = 1 THEN 1 ELSE 0 END)  AS submitted_count
        FROM runs r
        LEFT JOIN trajectories t ON t.run_id = r.id
        GROUP BY r.id
        ORDER BY r.id
        """
    )
    out: list[RunSummary] = []
    for r in rows:
        has_results = bool(r["has_results"])
        out.append(
            RunSummary(
                id=r["id"],
                relative_path=r["relative_path"],
                trajectory_count=r["trajectory_count"] or 0,
                resolved_count=r["resolved_count"] if has_results else None,
                submitted_count=r["submitted_count"] if has_results else None,
                has_results=has_results,
            )
        )
    return out


def list_trajectories(
    run_id: str,
    *,
    status_filter: StatusFilter = "any",
    exit_substring: str | None = None,
    search: str | None = None,
    cost_min: float | None = None,
    cost_max: float | None = None,
    sort: SortField = "id",
    order: SortOrder = "asc",
    limit: int = 1000,
    offset: int = 0,
) -> tuple[list[TrajectorySummary], int]:
    """Return (rows, total_count_before_pagination)."""
    if not db.fetch_one("SELECT 1 FROM runs WHERE id = ?", (run_id,)):
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    where: list[str] = ["run_id = ?"]
    params: list[Any] = [run_id]

    if status_filter == "resolved":
        where.append("eval_resolved = 1")
    elif status_filter == "submitted":
        where.append("eval_submitted = 1 AND (eval_resolved = 0 OR eval_resolved IS NULL)")
    elif status_filter == "failed":
        where.append("eval_completed = 1 AND (eval_resolved = 0 OR eval_resolved IS NULL)")
    elif status_filter == "unscored":
        where.append("eval_resolved IS NULL AND eval_submitted IS NULL AND eval_completed IS NULL")

    if exit_substring:
        where.append("exit_status LIKE ?")
        params.append(f"%{exit_substring}%")

    if search:
        like = f"%{search}%"
        where.append("(id LIKE ? OR problem_statement LIKE ?)")
        params.extend([like, like])

    if cost_min is not None:
        where.append("instance_cost >= ?")
        params.append(cost_min)

    if cost_max is not None:
        where.append("instance_cost <= ?")
        params.append(cost_max)

    where_sql = " AND ".join(where)

    allowed_sort: dict[str, str] = {
        "id": "id",
        "instance_cost": "instance_cost",
        "api_calls": "api_calls",
        "step_count": "step_count",
        "tokens_sent": "tokens_sent",
    }
    sort_col = allowed_sort.get(sort, "id")
    order_sql = "DESC" if order == "desc" else "ASC"

    total_row = db.fetch_one(
        f"SELECT COUNT(*) AS n FROM trajectories WHERE {where_sql}", tuple(params)
    )
    total = int(total_row["n"]) if total_row else 0

    rows = db.fetch_all(
        f"""
        SELECT
            id, run_id, relative_path, exit_status, api_calls, instance_cost,
            tokens_sent, tokens_received, step_count,
            eval_completed, eval_submitted, eval_resolved
        FROM trajectories
        WHERE {where_sql}
        ORDER BY {sort_col} {order_sql}, id ASC
        LIMIT ? OFFSET ?
        """,
        (*params, limit, offset),
    )

    out: list[TrajectorySummary] = [
        TrajectorySummary(
            id=r["id"],
            run_id=r["run_id"],
            relative_path=r["relative_path"],
            exit_status=r["exit_status"],
            api_calls=r["api_calls"],
            instance_cost=r["instance_cost"],
            tokens_sent=r["tokens_sent"],
            tokens_received=r["tokens_received"],
            step_count=r["step_count"] or 0,
            eval=_eval_from_row(r),
        )
        for r in rows
    ]
    return out, total


def run_stats(run_id: str) -> RunStats:
    if not db.fetch_one("SELECT 1 FROM runs WHERE id = ?", (run_id,)):
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    rows = db.fetch_all(
        """
        SELECT instance_cost, tokens_sent, tokens_received, api_calls, step_count,
               exit_status, eval_resolved, eval_submitted, eval_completed
        FROM trajectories
        WHERE run_id = ?
        """,
        (run_id,),
    )

    costs = [r["instance_cost"] for r in rows if r["instance_cost"] is not None]
    steps = [r["step_count"] or 0 for r in rows]
    resolved = sum(1 for r in rows if r["eval_resolved"] == 1)
    submitted = sum(1 for r in rows if r["eval_submitted"] == 1)
    completed = sum(1 for r in rows if r["eval_completed"] == 1)

    return RunStats(
        trajectory_count=len(rows),
        resolved_count=resolved,
        submitted_count=submitted,
        completed_count=completed,
        pass_rate=(resolved / completed) if completed else None,
        total_cost=sum(costs),
        mean_cost=statistics.fmean(costs) if costs else None,
        median_cost=statistics.median(costs) if costs else None,
        total_tokens_sent=sum(r["tokens_sent"] or 0 for r in rows),
        total_tokens_received=sum(r["tokens_received"] or 0 for r in rows),
        total_api_calls=sum(r["api_calls"] or 0 for r in rows),
        median_step_count=statistics.median(steps) if steps else None,
        p95_step_count=_percentile(steps, 0.95) if steps else None,
        exit_status_counts=dict(
            Counter(r["exit_status"] for r in rows if r["exit_status"])
        ),
    )


def _percentile(values: list[int], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round(p * (len(s) - 1)))))
    return float(s[k])


def get_trajectory(run_id: str, trajectory_id: str) -> TrajectoryDetail:
    row = db.fetch_one(
        "SELECT file_path, eval_completed, eval_submitted, eval_resolved "
        "FROM trajectories WHERE run_id = ? AND id = ?",
        (run_id, trajectory_id),
    )
    if not row:
        raise HTTPException(
            status_code=404, detail=f"Trajectory '{trajectory_id}' not found in '{run_id}'"
        )

    traj_path = Path(row["file_path"])
    _safe_join(_root(), str(traj_path.relative_to(_root())))  # path-traversal guard

    traj = _load_traj_file(traj_path)
    run_dir = _safe_join(_root(), run_id)

    problem_statement: str | None = None
    for msg in traj.history:
        if msg.role == "user" and msg.content:
            problem_statement = msg.content
            break

    return TrajectoryDetail(
        id=trajectory_id,
        run_id=run_id,
        relative_path=str(traj_path.relative_to(run_dir)),
        problem_statement=problem_statement,
        steps=traj.trajectory,
        info=traj.info,
        eval=_eval_from_row(row),
    )


def list_live(since_seconds: float = 60.0, limit: int = 50) -> list[LiveTrajectory]:
    """Trajectories whose mtime is within `since_seconds`. Ordered most-recent first."""
    import time

    cutoff = time.time() - since_seconds
    rows = db.fetch_all(
        """
        SELECT run_id, id, mtime, step_count, exit_status,
               eval_completed, eval_submitted, eval_resolved
        FROM trajectories
        WHERE mtime > ?
        ORDER BY mtime DESC
        LIMIT ?
        """,
        (cutoff, limit),
    )
    return [
        LiveTrajectory(
            run_id=r["run_id"],
            trajectory_id=r["id"],
            mtime=r["mtime"],
            step_count=r["step_count"] or 0,
            exit_status=r["exit_status"],
            eval=_eval_from_row(r),
        )
        for r in rows
    ]


def _parse_ref(ref: str) -> tuple[str, str]:
    if ":" not in ref:
        raise HTTPException(
            status_code=400,
            detail=f"Compare ref '{ref}' must be 'run_id:trajectory_id'",
        )
    run_id, traj_id = ref.split(":", 1)
    if not run_id or not traj_id:
        raise HTTPException(status_code=400, detail=f"Invalid compare ref '{ref}'")
    return run_id, traj_id


def _action_set(detail: TrajectoryDetail) -> set[str]:
    return {s.action.strip() for s in detail.steps if s.action.strip()}


def compare(a_ref: str, b_ref: str) -> CompareResult:
    run_a, traj_a = _parse_ref(a_ref)
    run_b, traj_b = _parse_ref(b_ref)
    a = get_trajectory(run_a, traj_a)
    b = get_trajectory(run_b, traj_b)

    actions_a = _action_set(a)
    actions_b = _action_set(b)
    union = actions_a | actions_b
    overlap = len(actions_a & actions_b) / len(union) if union else 0.0

    cost_a = a.info.model_stats.instance_cost
    cost_b = b.info.model_stats.instance_cost

    summary = CompareSummary(
        step_count_a=len(a.steps),
        step_count_b=len(b.steps),
        step_count_delta=len(b.steps) - len(a.steps),
        cost_a=cost_a,
        cost_b=cost_b,
        cost_delta=(cost_b - cost_a) if cost_a is not None and cost_b is not None else None,
        api_calls_a=a.info.model_stats.api_calls,
        api_calls_b=b.info.model_stats.api_calls,
        eval_resolved_a=a.eval.resolved,
        eval_resolved_b=b.eval.resolved,
        action_overlap_ratio=overlap,
    )
    return CompareResult(a=a, b=b, summary=summary, diff_analysis=_analyze_diffs(a, b))


def _analyze_diffs(a: TrajectoryDetail, b: TrajectoryDetail) -> DiffAnalysis | None:
    fa = diff_mod.parse_unified_diff(a.info.submission)
    fb = diff_mod.parse_unified_diff(b.info.submission)
    if not fa and not fb:
        return None
    merge = diff_mod.merge(fa, fb)
    union = merge.paths_a | merge.paths_b
    overlap_ratio = (len(merge.in_both) / len(union)) if union else 0.0

    files: list[DiffFileStat] = []
    for path in sorted(union):
        sa = fa.get(path)
        sb = fb.get(path)
        files.append(
            DiffFileStat(
                path=path,
                in_a=sa is not None,
                in_b=sb is not None,
                added_a=sa.added if sa else 0,
                removed_a=sa.removed if sa else 0,
                added_b=sb.added if sb else 0,
                removed_b=sb.removed if sb else 0,
            )
        )
    # Files touched by both sides first; then alphabetical.
    files.sort(key=lambda f: (not (f.in_a and f.in_b), f.path))

    return DiffAnalysis(
        files_a_count=len(merge.paths_a),
        files_b_count=len(merge.paths_b),
        files_in_both=len(merge.in_both),
        files_only_a=len(merge.only_a),
        files_only_b=len(merge.only_b),
        file_overlap_ratio=overlap_ratio,
        files=files,
    )


COST_BUCKETS: list[tuple[float, float | None, str]] = [
    (0.0, 0.05, "$0.00–0.05"),
    (0.05, 0.10, "$0.05–0.10"),
    (0.10, 0.25, "$0.10–0.25"),
    (0.25, 0.50, "$0.25–0.50"),
    (0.50, 1.00, "$0.50–1.00"),
    (1.00, None, "$1.00+"),
]

STEP_BUCKETS: list[tuple[int, int | None, str]] = [
    (1, 5, "1–5"),
    (6, 10, "6–10"),
    (11, 20, "11–20"),
    (21, 40, "21–40"),
    (41, None, "41+"),
]


def _bucket_cost(cost: float | None) -> tuple[float, float | None, str] | None:
    if cost is None:
        return None
    for lower, upper, label in COST_BUCKETS:
        if upper is None:
            if cost >= lower:
                return lower, upper, label
        elif lower <= cost < upper:
            return lower, upper, label
    return None


def _bucket_steps(steps: int) -> tuple[int, int | None, str] | None:
    if steps <= 0:
        return None
    for lower, upper, label in STEP_BUCKETS:
        if upper is None:
            if steps >= lower:
                return lower, upper, label
        elif lower <= steps <= upper:
            return lower, upper, label
    return None


def run_analytics(run_id: str) -> RunAnalytics:
    if not db.fetch_one("SELECT 1 FROM runs WHERE id = ?", (run_id,)):
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    rows = db.fetch_all(
        """
        SELECT id, instance_cost, step_count, api_calls, exit_status,
               eval_resolved
        FROM trajectories
        WHERE run_id = ?
        """,
        (run_id,),
    )

    # Cost histogram
    cost_counts: dict[str, tuple[int, float, float | None]] = {}
    for lower, upper, label in COST_BUCKETS:
        cost_counts[label] = (0, lower, upper)
    for r in rows:
        bucket = _bucket_cost(r["instance_cost"])
        if bucket:
            _, _, label = bucket
            count, lo, up = cost_counts[label]
            cost_counts[label] = (count + 1, lo, up)
    cost_histogram = [
        HistogramBin(label=label, count=c[0], lower=c[1], upper=c[2])
        for label, c in cost_counts.items()
    ]

    # Step histogram
    step_counts: dict[str, tuple[int, float, float | None]] = {}
    for lower, upper, label in STEP_BUCKETS:
        step_counts[label] = (0, float(lower), float(upper) if upper else None)
    for r in rows:
        bucket = _bucket_steps(r["step_count"] or 0)
        if bucket:
            _, _, label = bucket
            count, lo, up = step_counts[label]
            step_counts[label] = (count + 1, lo, up)
    step_histogram = [
        HistogramBin(label=label, count=c[0], lower=c[1], upper=c[2])
        for label, c in step_counts.items()
    ]

    # Pass rate by step bucket
    pass_by_bucket: dict[str, list[int]] = {label: [0, 0] for *_, label in STEP_BUCKETS}
    for r in rows:
        bucket = _bucket_steps(r["step_count"] or 0)
        if not bucket:
            continue
        _, _, label = bucket
        pass_by_bucket[label][0] += 1
        if r["eval_resolved"] == 1:
            pass_by_bucket[label][1] += 1
    pass_rate_by_step_bucket = [
        BucketPassRate(
            label=label,
            total=total,
            resolved=resolved,
            rate=(resolved / total) if total else None,
        )
        for label, (total, resolved) in pass_by_bucket.items()
    ]

    # Exit-status breakdown (resolved vs total per exit_status)
    es_totals: dict[str, list[int]] = {}
    for r in rows:
        es = r["exit_status"] or "unknown"
        slot = es_totals.setdefault(es, [0, 0])
        slot[0] += 1
        if r["eval_resolved"] == 1:
            slot[1] += 1
    exit_status_breakdown = [
        ExitStatusBreakdown(exit_status=es, total=t, resolved=res)
        for es, (t, res) in sorted(es_totals.items(), key=lambda x: -x[1][0])
    ]

    # Top costly
    top_costly_rows = db.fetch_all(
        """
        SELECT id, instance_cost, step_count, api_calls, exit_status, eval_resolved
        FROM trajectories
        WHERE run_id = ? AND instance_cost IS NOT NULL
        ORDER BY instance_cost DESC
        LIMIT 10
        """,
        (run_id,),
    )
    top_costly = [_to_top_traj(r) for r in top_costly_rows]

    # Top longest
    top_long_rows = db.fetch_all(
        """
        SELECT id, instance_cost, step_count, api_calls, exit_status, eval_resolved
        FROM trajectories
        WHERE run_id = ?
        ORDER BY step_count DESC, id ASC
        LIMIT 10
        """,
        (run_id,),
    )
    top_longest = [_to_top_traj(r) for r in top_long_rows]

    return RunAnalytics(
        cost_histogram=cost_histogram,
        step_histogram=step_histogram,
        pass_rate_by_step_bucket=pass_rate_by_step_bucket,
        exit_status_breakdown=exit_status_breakdown,
        top_costly=top_costly,
        top_longest=top_longest,
    )


def _to_top_traj(r: Any) -> TopTrajectory:
    resolved = r["eval_resolved"]
    return TopTrajectory(
        id=r["id"],
        instance_cost=r["instance_cost"],
        step_count=r["step_count"] or 0,
        api_calls=r["api_calls"],
        exit_status=r["exit_status"],
        eval_resolved=None if resolved is None else bool(resolved),
    )


def compare_runs(a_id: str, b_id: str) -> RunCompareResult:
    if a_id == b_id:
        raise HTTPException(status_code=400, detail="Cannot compare a run with itself")
    if not db.fetch_one("SELECT 1 FROM runs WHERE id = ?", (a_id,)):
        raise HTTPException(status_code=404, detail=f"Run '{a_id}' not found")
    if not db.fetch_one("SELECT 1 FROM runs WHERE id = ?", (b_id,)):
        raise HTTPException(status_code=404, detail=f"Run '{b_id}' not found")

    def _load(run_id: str) -> dict[str, Any]:
        rows = db.fetch_all(
            """
            SELECT id, instance_cost, step_count, exit_status,
                   eval_completed, eval_submitted, eval_resolved
            FROM trajectories WHERE run_id = ?
            """,
            (run_id,),
        )
        return {r["id"]: r for r in rows}

    a_map = _load(a_id)
    b_map = _load(b_id)

    all_ids = sorted(set(a_map) | set(b_map))

    instances: list[InstanceCompareRow] = []
    resolved_only_a = resolved_only_b = resolved_in_both = failed_in_both = 0
    divergent = 0

    def _side(row: Any) -> InstanceSide:
        if row is None:
            return InstanceSide(present=False)
        def b(v: int | None) -> bool | None:
            return None if v is None else bool(v)
        return InstanceSide(
            present=True,
            eval_resolved=b(row["eval_resolved"]),
            eval_submitted=b(row["eval_submitted"]),
            eval_completed=b(row["eval_completed"]),
            exit_status=row["exit_status"],
            instance_cost=row["instance_cost"],
            step_count=row["step_count"] or 0,
        )

    for iid in all_ids:
        ra = a_map.get(iid)
        rb = b_map.get(iid)
        side_a = _side(ra)
        side_b = _side(rb)

        is_diverg = side_a.eval_resolved != side_b.eval_resolved
        if is_diverg:
            divergent += 1
            if side_a.eval_resolved and not side_b.eval_resolved:
                resolved_only_a += 1
            elif side_b.eval_resolved and not side_a.eval_resolved:
                resolved_only_b += 1
        else:
            if side_a.eval_resolved is True:
                resolved_in_both += 1
            elif side_a.eval_resolved is False and side_b.eval_resolved is False:
                failed_in_both += 1

        cost_delta: float | None = None
        if side_a.instance_cost is not None and side_b.instance_cost is not None:
            cost_delta = side_b.instance_cost - side_a.instance_cost

        instances.append(
            InstanceCompareRow(
                id=iid,
                in_a=side_a,
                in_b=side_b,
                divergent=is_diverg,
                cost_delta=cost_delta,
            )
        )

    a_only = sum(1 for iid in all_ids if iid in a_map and iid not in b_map)
    b_only = sum(1 for iid in all_ids if iid in b_map and iid not in a_map)
    in_both = sum(1 for iid in all_ids if iid in a_map and iid in b_map)

    total_cost_a = sum((r["instance_cost"] or 0.0) for r in a_map.values())
    total_cost_b = sum((r["instance_cost"] or 0.0) for r in b_map.values())

    summary = RunCompareSummary(
        a_id=a_id,
        b_id=b_id,
        instances_in_a_only=a_only,
        instances_in_b_only=b_only,
        instances_in_both=in_both,
        resolved_only_a=resolved_only_a,
        resolved_only_b=resolved_only_b,
        resolved_in_both=resolved_in_both,
        failed_in_both=failed_in_both,
        divergent_count=divergent,
        total_cost_a=total_cost_a,
        total_cost_b=total_cost_b,
        cost_delta=total_cost_b - total_cost_a,
    )

    # Order: divergent first, then by id
    instances.sort(key=lambda r: (not r.divergent, r.id))

    return RunCompareResult(summary=summary, instances=instances)


@lru_cache(maxsize=1)
def root_diagnostics() -> tuple[str, bool]:
    root = _root()
    return str(root), root.exists()
