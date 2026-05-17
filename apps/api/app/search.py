"""Full-text search over trajectories and annotations using SQLite FTS5."""

from __future__ import annotations

import re

from fastapi import HTTPException

from app import db
from app.schemas import SearchHit, SearchResult

# FTS5 reserves these and choking on punctuation is the most common footgun
# when users type queries naturally. We sanitize so single-word queries always
# work and lightly tolerate special tokens.
_FTS5_SPECIAL = re.compile(r"[\"'^*:()]")


def _sanitize(query: str) -> str:
    cleaned = _FTS5_SPECIAL.sub(" ", query).strip()
    if not cleaned:
        return cleaned
    # Quote each whitespace-separated token so users get phrase-aware matching
    # without learning FTS5's mini-language.
    tokens = [f'"{t}"' for t in cleaned.split() if t]
    return " ".join(tokens)


def search(
    query: str,
    *,
    run_id: str | None = None,
    kind: str = "all",
    limit: int = 50,
) -> SearchResult:
    if not query.strip():
        return SearchResult(query=query, hits=[], total=0)
    if kind not in ("all", "trajectory", "annotation"):
        raise HTTPException(status_code=400, detail="kind must be one of: all|trajectory|annotation")

    match = _sanitize(query)
    if not match:
        return SearchResult(query=query, hits=[], total=0)

    hits: list[SearchHit] = []

    if kind in ("all", "trajectory"):
        traj_sql = """
            SELECT
                run_id,
                trajectory_id,
                bm25(trajectories_fts) AS score,
                snippet(trajectories_fts, 2, '[', ']', '…', 8) AS instance_snip,
                snippet(trajectories_fts, 3, '[', ']', '…', 8) AS problem_snip,
                snippet(trajectories_fts, 4, '[', ']', '…', 12) AS step_snip
            FROM trajectories_fts
            WHERE trajectories_fts MATCH ?
        """
        params: list[object] = [match]
        if run_id:
            traj_sql += " AND run_id = ?"
            params.append(run_id)
        traj_sql += " ORDER BY score LIMIT ?"
        params.append(limit)

        try:
            traj_rows = db.fetch_all(traj_sql, tuple(params))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Search query rejected by FTS5: {exc}") from exc

        for r in traj_rows:
            # Pick the most informative non-empty snippet.
            field, snip = _best_snippet(
                ("instance_id", r["instance_snip"]),
                ("step_text", r["step_snip"]),
                ("problem", r["problem_snip"]),
            )
            hits.append(
                SearchHit(
                    kind="trajectory",
                    run_id=r["run_id"],
                    trajectory_id=r["trajectory_id"],
                    field=field,
                    snippet=snip,
                    score=float(r["score"]),
                )
            )

    if kind in ("all", "annotation"):
        ann_sql = """
            SELECT
                run_id,
                trajectory_id,
                step_index,
                bm25(annotations_fts) AS score,
                snippet(annotations_fts, 4, '[', ']', '…', 12) AS body_snip
            FROM annotations_fts
            WHERE annotations_fts MATCH ?
        """
        params = [match]
        if run_id:
            ann_sql += " AND run_id = ?"
            params.append(run_id)
        ann_sql += " ORDER BY score LIMIT ?"
        params.append(limit)

        try:
            ann_rows = db.fetch_all(ann_sql, tuple(params))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Search query rejected by FTS5: {exc}") from exc

        for r in ann_rows:
            step_idx = r["step_index"]
            hits.append(
                SearchHit(
                    kind="annotation",
                    run_id=r["run_id"],
                    trajectory_id=r["trajectory_id"],
                    step_index=None if step_idx == -1 else int(step_idx),
                    field="annotation_body",
                    snippet=r["body_snip"],
                    score=float(r["score"]),
                )
            )

    hits.sort(key=lambda h: h.score)
    hits = hits[:limit]
    return SearchResult(query=query, hits=hits, total=len(hits))


def _best_snippet(*candidates: tuple[str, str]) -> tuple[str, str]:
    # FTS5 returns the source text when no token in that column matched, so
    # prefer the snippets that actually contain the [highlight] markers.
    for field, snip in candidates:
        if "[" in (snip or ""):
            return field, snip
    return candidates[0][0], candidates[0][1] or ""
