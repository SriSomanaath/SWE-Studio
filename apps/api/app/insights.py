"""Trajectory clustering + similarity, hand-rolled on top of SQLite + FTS5."""

from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from typing import Any

from fastapi import HTTPException

from app import db, embeddings
from app.schemas import RunInsights, SimilarHit, TrajectoryCluster
from app.trajectory_store import get_trajectory

# Drop hyper-common tokens that don't differentiate trajectories.
_STOPWORDS = {"the", "a", "an", "to", "in", "on", "of", "for", "and", "or"}

_WORD_RE = re.compile(r"[A-Za-z_][\w.\-/]*")

# FTS5-safe identifiers (letters, digits, underscore, dash). Anything outside
# this is dropped from OR-joined similarity queries to avoid syntax errors.
_FTS_SAFE = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]*$")


def _verb(action: str) -> str:
    """First meaningful token of an action line — the verb."""
    for raw in action.strip().split():
        cleaned = raw.strip("`'\"$();,").lower()
        if cleaned and cleaned not in _STOPWORDS:
            return cleaned[:24]
    return ""


def _fingerprint(actions: list[str], n: int = 3) -> str:
    """Top-n distinct action verbs, joined by `·` — a coarse strategy signature."""
    verbs = [_verb(a) for a in actions if a.strip()]
    verbs = [v for v in verbs if v]
    counts = Counter(verbs)
    top = [v for v, _ in counts.most_common(n)]
    return "·".join(top) if top else "(empty)"


def run_insights(run_id: str) -> RunInsights:
    if not db.fetch_one("SELECT 1 FROM runs WHERE id = ?", (run_id,)):
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    rows = db.fetch_all(
        """
        SELECT id, step_count, instance_cost,
               eval_resolved, eval_submitted, eval_completed
        FROM trajectories
        WHERE run_id = ?
        """,
        (run_id,),
    )

    # We read action text directly from each .traj — this is correct (we never
    # conflate thought/observation tokens) and the trajectory_store layer
    # already path-validates so we avoid any directory-traversal risk. The
    # alternative (storing actions in a dedicated FTS column) would need a
    # schema bump for a marginal speed-up.
    by_print: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        detail = get_trajectory(run_id, r["id"])
        actions = [s.action for s in detail.steps if s.action.strip()]
        fp = _fingerprint(actions)
        by_print[fp].append(
            {
                "id": r["id"],
                "step_count": r["step_count"] or 0,
                "cost": r["instance_cost"],
                "resolved": r["eval_resolved"] == 1,
                "submitted": r["eval_submitted"] == 1,
                "completed": r["eval_completed"] == 1,
            }
        )

    clusters: list[TrajectoryCluster] = []
    for fp, members in by_print.items():
        steps = [m["step_count"] for m in members]
        costs = [m["cost"] for m in members if m["cost"] is not None]
        resolved = sum(1 for m in members if m["resolved"])
        submitted = sum(1 for m in members if m["submitted"] and not m["resolved"])
        failed = sum(1 for m in members if m["completed"] and not m["resolved"])
        clusters.append(
            TrajectoryCluster(
                fingerprint=fp,
                size=len(members),
                resolved_count=resolved,
                submitted_count=submitted,
                failed_count=failed,
                median_step_count=statistics.median(steps) if steps else None,
                mean_cost=statistics.fmean(costs) if costs else None,
                sample_ids=[m["id"] for m in members[:5]],
            )
        )

    # Largest cluster first; then highest pass-rate, then alphabetic.
    clusters.sort(
        key=lambda c: (-c.size, -(c.resolved_count / c.size if c.size else 0), c.fingerprint)
    )

    return RunInsights(
        run_id=run_id,
        trajectory_count=len(rows),
        clusters=clusters,
    )


def _split_actions(step_text: str) -> list[str]:
    """The indexer joins thought/action/observation with newlines, so each line
    is a candidate action. We pick the lines that look like commands by checking
    for at least one common shell verb at the start — anything else is dropped."""
    out: list[str] = []
    for line in step_text.splitlines():
        if line.strip():
            out.append(line)
    return out


def find_similar(
    run_id: str,
    trajectory_id: str,
    limit: int = 10,
    mode: str = "auto",
) -> list[SimilarHit]:
    """`mode` is one of:

    * `auto` — semantic if any embedding exists for the source, else FTS5.
    * `semantic` — embedding-cosine only; returns [] when unavailable.
    * `fts` — Phase 9's FTS5 token-overlap approach.
    """
    if mode not in {"auto", "semantic", "fts"}:
        raise HTTPException(status_code=400, detail="mode must be auto|semantic|fts")
    if not db.fetch_one(
        "SELECT 1 FROM trajectories WHERE run_id = ? AND id = ?",
        (run_id, trajectory_id),
    ):
        raise HTTPException(
            status_code=404,
            detail=f"Trajectory '{trajectory_id}' not found (run '{run_id}')",
        )

    if mode in ("auto", "semantic"):
        emb_hits = embeddings.find_similar(run_id, trajectory_id, limit=limit)
        if emb_hits:
            return [
                SimilarHit(
                    run_id=r, trajectory_id=t,
                    score=score, snippet=f"semantic cosine: {score:.3f}",
                )
                for r, t, score in emb_hits
            ]
        if mode == "semantic":
            return []

    detail = get_trajectory(run_id, trajectory_id)
    action_text = "\n".join(s.action for s in detail.steps if s.action.strip())

    # Tokens come from the actions first; fall back to the problem statement
    # if the trajectory had no commands (rare, but happens for forfeits).
    tokens = _candidate_tokens(action_text)
    if not tokens and detail.problem_statement:
        tokens = _candidate_tokens(detail.problem_statement)
    if not tokens:
        return []

    # OR-join so trajectories that share *any* of the source's distinctive
    # tokens are candidates. The bm25 rank then surfaces those that share the
    # most.
    match = " OR ".join(f'"{t}"' for t in tokens if _FTS_SAFE.match(t))
    if not match:
        return []

    rows = db.fetch_all(
        """
        SELECT run_id, trajectory_id, bm25(trajectories_fts) AS score,
               snippet(trajectories_fts, 4, '[', ']', '…', 10) AS snip
        FROM trajectories_fts
        WHERE trajectories_fts MATCH ?
        ORDER BY score
        LIMIT ?
        """,
        (match, limit + 1),
    )

    hits: list[SimilarHit] = []
    for r in rows:
        if r["run_id"] == run_id and r["trajectory_id"] == trajectory_id:
            continue
        hits.append(
            SimilarHit(
                run_id=r["run_id"],
                trajectory_id=r["trajectory_id"],
                score=-float(r["score"]),
                snippet=r["snip"] or "",
            )
        )
        if len(hits) >= limit:
            break
    return hits


def _candidate_tokens(text: str, max_tokens: int = 20) -> list[str]:
    counts: Counter[str] = Counter()
    for w in _WORD_RE.findall(text):
        lower = w.lower()
        if len(lower) < 4 or lower in _STOPWORDS:
            continue
        counts[lower] += 1
    return [tok for tok, _ in counts.most_common(max_tokens)]
