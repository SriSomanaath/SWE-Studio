"""Markdown export of a trajectory + its annotations."""

from __future__ import annotations

from io import StringIO

from fastapi import APIRouter, Response

from app import annotations as notes_svc
from app.trajectory_store import get_trajectory

router = APIRouter(tags=["export"])


@router.get(
    "/runs/{run_id}/trajectories/{trajectory_id}/export.md",
    response_class=Response,
)
def export_markdown(run_id: str, trajectory_id: str) -> Response:
    detail = get_trajectory(run_id, trajectory_id)
    notes = notes_svc.list_annotations(run_id, trajectory_id)

    by_step: dict[int, list] = {}
    traj_level = []
    for n in notes:
        if n.step_index == -1:
            traj_level.append(n)
        else:
            by_step.setdefault(n.step_index, []).append(n)

    out = StringIO()
    out.write(f"# {detail.run_id} · {detail.id}\n\n")
    if detail.info.exit_status:
        out.write(f"**Exit status:** `{detail.info.exit_status}`  \n")
    stats = detail.info.model_stats
    out.write(
        f"**Steps:** {len(detail.steps)} · **Cost:** "
        f"${stats.instance_cost:.2f} · **API calls:** {stats.api_calls}\n\n"
        if stats.instance_cost is not None and stats.api_calls is not None
        else f"**Steps:** {len(detail.steps)}\n\n"
    )

    if detail.eval.resolved is not None:
        out.write(
            "**Eval:** " + ("✅ resolved" if detail.eval.resolved else "❌ not resolved") + "\n\n"
        )

    if detail.problem_statement:
        out.write("## Problem statement\n\n")
        out.write(_fence(detail.problem_statement, "text"))
        out.write("\n")

    if traj_level:
        out.write("## Notes\n\n")
        for n in traj_level:
            out.write(f"- **{n.author}**: {n.body}\n")
        out.write("\n")

    for i, step in enumerate(detail.steps):
        out.write(f"## Step {i + 1}\n\n")
        if step.thought:
            out.write(f"> {step.thought.replace(chr(10), chr(10) + '> ')}\n\n")
        if step.action:
            out.write("**Action**\n\n")
            out.write(_fence(step.action, "bash"))
            out.write("\n")
        if step.observation:
            out.write("**Observation**\n\n")
            out.write(_fence(step.observation, "text"))
            out.write("\n")
        for n in by_step.get(i, []):
            out.write(f"> _Note from {n.author}:_ {n.body}\n\n")

    if detail.info.submission:
        out.write("## Final patch\n\n")
        out.write(_fence(detail.info.submission, "diff"))
        out.write("\n")

    return Response(
        content=out.getvalue(),
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{trajectory_id}.md"',
        },
    )


def _fence(text: str, lang: str = "") -> str:
    return f"```{lang}\n{text.rstrip()}\n```\n"
