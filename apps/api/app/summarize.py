"""Trajectory summary service.

Two providers:

* `heuristic` — deterministic, dependency-free. Counts step actions, extracts
  the problem statement, lists touched files from the submission diff, and
  composes a short paragraph.
* `ai` — optional. When `ANTHROPIC_API_KEY` is set, sends the trajectory's
  flattened text to Anthropic and returns the model's summary. Falls back to
  the heuristic provider if the SDK isn't installed or the call fails.

Each summary is cached in SQLite keyed by `(run_id, trajectory_id, provider)`,
and persisted as an annotation by `@studio-ai` so it shows up inline on the
trajectory page through the existing annotations UI.
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from typing import Any, Literal

from fastapi import HTTPException

from app import db, diff
from app.config import settings
from app.observability import metrics
from app.schemas import TrajectoryDetail, AISummary
from app.trajectory_store import get_trajectory

logger = logging.getLogger(__name__)

SUMMARY_AUTHOR = "@studio-ai"
ProviderName = Literal["heuristic", "ai"]


# --- Cache layer -----------------------------------------------------------


def _cache_get(run_id: str, trajectory_id: str, provider: ProviderName) -> AISummary | None:
    row = db.fetch_one(
        "SELECT body, model, created_at FROM summaries "
        "WHERE run_id = ? AND trajectory_id = ? AND provider = ?",
        (run_id, trajectory_id, provider),
    )
    if not row:
        return None
    return AISummary(
        run_id=run_id,
        trajectory_id=trajectory_id,
        provider=provider,
        body=row["body"],
        model=row["model"],
        created_at=row["created_at"],
        cached=True,
    )


def _cache_put(summary: AISummary) -> None:
    with db.write_tx() as conn:
        conn.execute(
            """
            INSERT INTO summaries (run_id, trajectory_id, provider, body, model, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, trajectory_id, provider) DO UPDATE SET
                body = excluded.body,
                model = excluded.model,
                created_at = excluded.created_at
            """,
            (
                summary.run_id,
                summary.trajectory_id,
                summary.provider,
                summary.body,
                summary.model,
                summary.created_at,
            ),
        )


# --- Annotation mirror -----------------------------------------------------


def _upsert_summary_annotation(summary: AISummary) -> None:
    """Persist (or replace) the summary as an annotation by @studio-ai so it
    shows up inline on the trajectory page."""
    body = f"_{summary.provider.upper()} summary"
    if summary.model:
        body += f" · {summary.model}"
    body += f"_\n\n{summary.body}"

    with db.write_tx() as conn:
        rows = conn.execute(
            "SELECT id FROM annotations WHERE run_id = ? AND trajectory_id = ? "
            "AND step_index = -1 AND author = ?",
            (summary.run_id, summary.trajectory_id, SUMMARY_AUTHOR),
        ).fetchall()
        for r in rows:
            conn.execute("DELETE FROM annotations WHERE id = ?", (r["id"],))
            conn.execute(
                "DELETE FROM annotations_fts WHERE annotation_id = ?", (r["id"],)
            )
        now = time.time()
        cur = conn.execute(
            """
            INSERT INTO annotations
                (run_id, trajectory_id, step_index, author, body, created_at, updated_at)
            VALUES (?, ?, -1, ?, ?, ?, ?)
            """,
            (summary.run_id, summary.trajectory_id, SUMMARY_AUTHOR, body, now, now),
        )
        conn.execute(
            """
            INSERT INTO annotations_fts
                (annotation_id, run_id, trajectory_id, step_index, body)
            VALUES (?, ?, ?, -1, ?)
            """,
            (cur.lastrowid, summary.run_id, summary.trajectory_id, body),
        )


# --- Heuristic provider ----------------------------------------------------


def _heuristic_body(detail: TrajectoryDetail) -> str:
    n_steps = len(detail.steps)
    exit_status = detail.info.exit_status or "unknown"
    eval_phrase = (
        "marked resolved by the benchmark"
        if detail.eval.resolved
        else "submitted but not resolved"
        if detail.eval.submitted
        else "did not produce a resolved patch"
    )

    actions = [s.action.split("\n", 1)[0].strip() for s in detail.steps if s.action.strip()]
    top_actions = Counter(_first_token(a) for a in actions if a).most_common(5)
    actions_clause = (
        ", ".join(f"`{tok}` ({n})" for tok, n in top_actions) if top_actions else "no actions"
    )

    submission_files = diff.parse_unified_diff(detail.info.submission)
    if submission_files:
        files_line = (
            "The submitted patch touches "
            + ", ".join(f"`{p}`" for p in list(submission_files)[:6])
            + (" (…)" if len(submission_files) > 6 else "")
            + "."
        )
    else:
        files_line = "No patch was submitted."

    problem = (detail.problem_statement or "").strip()
    if problem:
        problem = problem.replace("\n", " ")
        if len(problem) > 240:
            problem = problem[:237] + "…"
        problem_line = f"Problem: {problem}"
    else:
        problem_line = "No problem statement recorded."

    stats = detail.info.model_stats
    cost = f"${stats.instance_cost:.2f}" if stats.instance_cost is not None else "—"
    tokens = (
        f"{(stats.tokens_sent or 0):,} in / {(stats.tokens_received or 0):,} out"
        if stats.tokens_sent or stats.tokens_received
        else "—"
    )

    return (
        f"{problem_line}\n\n"
        f"Outcome: agent took {n_steps} steps, exited with `{exit_status}`; {eval_phrase}.\n"
        f"Top action verbs: {actions_clause}.\n"
        f"{files_line}\n"
        f"Cost: {cost} · Tokens: {tokens}."
    )


def _first_token(s: str) -> str:
    for tok in s.strip().split():
        cleaned = tok.strip("`'\"$")
        if cleaned:
            return cleaned[:24]
    return "?"


# --- AI provider -----------------------------------------------------------


def _ai_body(detail: TrajectoryDetail) -> tuple[str, str]:
    """Returns (body, model_name). Raises HTTPException on configuration miss."""
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not configured — use provider=heuristic instead.",
        )
    try:
        from anthropic import Anthropic  # type: ignore[import-not-found]
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="anthropic package not installed; `pip install anthropic` or use heuristic.",
        ) from exc

    client = Anthropic(api_key=settings.anthropic_api_key)
    prompt = _build_prompt(detail)
    try:
        resp = client.messages.create(
            model=settings.summary_model,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        logger.exception("Anthropic call failed")
        raise HTTPException(status_code=502, detail=f"Anthropic call failed: {exc}") from exc

    parts: list[str] = []
    for block in resp.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    body = "\n".join(parts).strip()
    if not body:
        raise HTTPException(status_code=502, detail="Anthropic returned an empty summary")
    return body, settings.summary_model


def _build_prompt(detail: TrajectoryDetail) -> str:
    step_lines: list[str] = []
    for i, step in enumerate(detail.steps[:60]):  # cap to keep prompts bounded
        action = step.action.strip().split("\n", 1)[0][:200]
        obs = step.observation.strip().split("\n", 1)[0][:160]
        step_lines.append(f"Step {i + 1}: {action} -> {obs}")
    return (
        "You are summarizing a coding-agent trajectory for engineers reviewing"
        " an agent benchmark run. Write 4–6 sentences capturing: the problem, the"
        " agent's strategy, where it spent effort, and whether it succeeded."
        " Stay factual; don't invent details.\n\n"
        f"Problem statement:\n{detail.problem_statement or 'unknown'}\n\n"
        f"Exit status: {detail.info.exit_status}\n"
        f"Eval resolved: {detail.eval.resolved}\n"
        f"Steps ({len(detail.steps)}):\n"
        + "\n".join(step_lines)
        + (f"\n\nSubmitted patch:\n{detail.info.submission[:2000]}"
           if detail.info.submission else "\n\nNo submission was produced.")
    )


# --- Public API ------------------------------------------------------------


def summarize(
    run_id: str,
    trajectory_id: str,
    provider: ProviderName = "heuristic",
    *,
    force: bool = False,
) -> AISummary:
    if provider not in ("heuristic", "ai"):
        raise HTTPException(status_code=400, detail="provider must be heuristic or ai")

    if not force:
        cached = _cache_get(run_id, trajectory_id, provider)
        if cached:
            return cached

    detail = get_trajectory(run_id, trajectory_id)

    if provider == "heuristic":
        body = _heuristic_body(detail)
        summary = AISummary(
            run_id=run_id,
            trajectory_id=trajectory_id,
            provider="heuristic",
            body=body,
            model=None,
            created_at=time.time(),
            cached=False,
        )
    else:
        body, model = _ai_body(detail)
        summary = AISummary(
            run_id=run_id,
            trajectory_id=trajectory_id,
            provider="ai",
            body=body,
            model=model,
            created_at=time.time(),
            cached=False,
        )

    _cache_put(summary)
    _upsert_summary_annotation(summary)
    metrics.inc("ai_summaries_total", provider=provider)
    return summary


def is_ai_available() -> bool:
    return bool(settings.anthropic_api_key)
