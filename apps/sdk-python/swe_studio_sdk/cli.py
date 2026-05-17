"""Terminal CLI for SWE Studio.

Installed as `swe-studio` by `swe-studio-sdk`. Talks to the API over HTTP via
the bundled :class:`StudioClient` so the same package serves both the
agent-instrumentation use case (push trajectories) and the developer-ergonomics
use case (browse + manage from a terminal).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from .client import StudioClient

_DEFAULT_BASE = os.environ.get("SWE_STUDIO_API_URL", "http://127.0.0.1:8080")


def _print_table(rows: list[dict[str, Any]], cols: list[tuple[str, str]]) -> None:
    """rows: list of dicts; cols: list of (header, key)."""
    if not rows:
        print("(no rows)")
        return
    widths = [max(len(h), *(len(str(r.get(k, ""))) for r in rows)) for h, k in cols]
    sep = "  "
    print(sep.join(h.ljust(w) for (h, _), w in zip(cols, widths)))
    print(sep.join("-" * w for w in widths))
    for r in rows:
        print(sep.join(str(r.get(k, "")).ljust(w) for (_, k), w in zip(cols, widths)))


# --- subcommands -----------------------------------------------------------


def cmd_runs_ls(args: argparse.Namespace, client: StudioClient) -> int:
    res = client._client.get("/runs")
    res.raise_for_status()
    _print_table(
        res.json(),
        [("ID", "id"), ("TRAJ", "trajectory_count"), ("RESOLVED", "resolved_count")],
    )
    return 0


def cmd_traj_show(args: argparse.Namespace, client: StudioClient) -> int:
    res = client._client.get(f"/runs/{args.run_id}/trajectories/{args.trajectory_id}")
    res.raise_for_status()
    body = res.json()
    info = body.get("info") or {}
    stats = info.get("model_stats") or {}
    print(f"# {body['run_id']} · {body['id']}")
    print(f"exit: {info.get('exit_status')}  resolved: {body.get('eval', {}).get('resolved')}")
    print(f"steps: {len(body.get('steps', []))}  cost: ${stats.get('instance_cost')}")
    if body.get("problem_statement"):
        print()
        print("## problem")
        print(body["problem_statement"][:600])
    for i, step in enumerate(body.get("steps", [])):
        print()
        print(f"## step {i + 1}")
        if step.get("action"):
            print(f"$ {step['action'].splitlines()[0]}")
    return 0


def cmd_search(args: argparse.Namespace, client: StudioClient) -> int:
    params = {"q": args.q, "limit": args.limit}
    if args.run_id:
        params["run_id"] = args.run_id
    res = client._client.get("/search", params=params)
    res.raise_for_status()
    body = res.json()
    rows = [
        {
            "kind": h["kind"],
            "ref": f"{h['run_id']}:{h['trajectory_id']}"
            + (f" #step{h['step_index'] + 1}" if h.get("step_index") is not None else ""),
            "snippet": (h.get("snippet") or "").replace("\n", " ")[:80],
        }
        for h in body["hits"]
    ]
    _print_table(rows, [("KIND", "kind"), ("REF", "ref"), ("SNIPPET", "snippet")])
    return 0


def cmd_summarize(args: argparse.Namespace, client: StudioClient) -> int:
    res = client._client.post(
        f"/runs/{args.run_id}/trajectories/{args.trajectory_id}/summarize",
        params={"provider": args.provider, "force": str(args.force).lower()},
    )
    res.raise_for_status()
    body = res.json()
    print(body["body"])
    print()
    print(f"(provider: {body['provider']} · cached: {body['cached']})", file=sys.stderr)
    return 0


def cmd_curate_add(args: argparse.Namespace, client: StudioClient) -> int:
    payload = {
        "slug": args.slug,
        "run_id": args.run_id,
        "trajectory_id": args.trajectory_id,
        "title": args.title,
        "description": args.description,
        "pinned_step": args.step,
    }
    headers = {"X-Author": args.author} if args.author else {}
    res = client._client.post("/showcase", json=payload, headers=headers)
    if res.status_code >= 400:
        print(f"error {res.status_code}: {res.text}", file=sys.stderr)
        return 1
    print(f"created /showcase/{res.json()['slug']}")
    return 0


def cmd_curate_ls(args: argparse.Namespace, client: StudioClient) -> int:
    res = client._client.get("/showcase")
    res.raise_for_status()
    _print_table(
        res.json(),
        [("SLUG", "slug"), ("REF", "run_id"), ("TITLE", "title")],
    )
    return 0


def cmd_curate_rm(args: argparse.Namespace, client: StudioClient) -> int:
    res = client._client.delete(f"/showcase/{args.slug}")
    if res.status_code == 204:
        print(f"deleted {args.slug}")
        return 0
    print(f"error {res.status_code}: {res.text}", file=sys.stderr)
    return 1


def cmd_webhook_ls(args: argparse.Namespace, client: StudioClient) -> int:
    res = client._client.get("/webhooks")
    res.raise_for_status()
    rows = [
        {
            "id": w["id"],
            "url": w["url"],
            "events": ",".join(w["events"]) if w["events"] else "*",
            "active": "✓" if w["active"] else "✗",
        }
        for w in res.json()
    ]
    _print_table(rows, [("ID", "id"), ("ACTIVE", "active"), ("EVENTS", "events"), ("URL", "url")])
    return 0


def cmd_webhook_add(args: argparse.Namespace, client: StudioClient) -> int:
    events = args.events.split(",") if args.events else []
    res = client._client.post(
        "/webhooks",
        json={"url": args.url, "events": events, "description": args.description},
    )
    if res.status_code >= 400:
        print(f"error {res.status_code}: {res.text}", file=sys.stderr)
        return 1
    body = res.json()
    print(f"created webhook #{body['id']}")
    print(f"secret: {body['secret']}", file=sys.stderr)
    return 0


def cmd_webhook_rm(args: argparse.Namespace, client: StudioClient) -> int:
    res = client._client.delete(f"/webhooks/{args.id}")
    if res.status_code == 204:
        print(f"deleted webhook #{args.id}")
        return 0
    print(f"error {res.status_code}: {res.text}", file=sys.stderr)
    return 1


def cmd_agent_run(args: argparse.Namespace, client: StudioClient) -> int:
    payload = {
        "problem": args.problem,
        "repo": os.path.abspath(args.repo),
        "model": args.model,
        "max_steps": args.max_steps,
        "max_cost_usd": args.max_cost,
    }
    if args.run_id:
        payload["run_id"] = args.run_id
    if args.trajectory_id:
        payload["trajectory_id"] = args.trajectory_id
    if getattr(args, "docker_image", None):
        payload["docker_image"] = args.docker_image
    res = client._client.post("/agent/run", json=payload, timeout=30.0)
    if res.status_code >= 400:
        print(f"error {res.status_code}: {res.text}", file=sys.stderr)
        return 1
    body = res.json()
    print(f"started agent on {body['run_id']}:{body['trajectory_id']}")
    print(f"trajectory: {client.base_url}{body['trajectory_url']}", file=sys.stderr)
    print(f".traj: {body['file_path']}", file=sys.stderr)
    return 0


def cmd_agent_ensemble(args: argparse.Namespace, client: StudioClient) -> int:
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    payload = {
        "problem": args.problem,
        "repo": os.path.abspath(args.repo),
        "models": models,
        "max_steps": args.max_steps,
        "max_cost_usd": args.max_cost,
    }
    if getattr(args, "docker_image", None):
        payload["docker_image"] = args.docker_image
    res = client._client.post("/agent/ensemble", json=payload, timeout=30.0)
    if res.status_code >= 400:
        print(f"error {res.status_code}: {res.text}", file=sys.stderr)
        return 1
    body = res.json()
    print(f"started ensemble {body['run_id']} with {len(body['trajectories'])} models")
    for t in body["trajectories"]:
        print(f"  {client.base_url}{t['trajectory_url']}", file=sys.stderr)
    return 0


def cmd_bench_run(args: argparse.Namespace, client: StudioClient) -> int:
    """Drive the agent across a JSONL of instances.

    Each line of the input must contain `instance_id`, `problem_statement`,
    and `repo_path`. The harness copies each repo to a fresh workdir per
    instance and POSTs `/agent/run` against a shared `run_id`, so Studio's
    indexer + analytics + run-vs-run compare light up for the whole batch.
    """
    import json
    import shutil
    import tempfile

    instances_path = os.path.abspath(args.instances)
    if not os.path.exists(instances_path):
        print(f"instances file not found: {instances_path}", file=sys.stderr)
        return 1
    instances: list[dict] = []
    with open(instances_path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                instances.append(json.loads(line))
    if args.limit:
        instances = instances[: args.limit]
    if not instances:
        print("no instances to run", file=sys.stderr)
        return 0

    timestamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    run_id = args.run_id or f"bench-{timestamp}"
    print(
        f"starting {len(instances)} instances under run {run_id} on {args.model}",
        file=sys.stderr,
    )

    started: list[str] = []
    for inst in instances:
        instance_id = inst.get("instance_id") or inst.get("id")
        problem = inst.get("problem_statement") or inst.get("problem") or ""
        repo_src = inst.get("repo_path") or inst.get("repo")
        if not instance_id or not repo_src:
            print(f"  skipping instance — missing fields: {inst}", file=sys.stderr)
            continue
        workdir = tempfile.mkdtemp(prefix=f"swe-studio-bench-{instance_id}-")
        shutil.copytree(repo_src, workdir, dirs_exist_ok=True)
        payload = {
            "problem": problem,
            "repo": workdir,
            "model": args.model,
            "run_id": run_id,
            "trajectory_id": instance_id,
            "max_steps": args.max_steps,
            "max_cost_usd": args.max_cost,
        }
        if getattr(args, "docker_image", None):
            payload["docker_image"] = args.docker_image
        res = client._client.post("/agent/run", json=payload, timeout=30.0)
        if res.status_code >= 400:
            print(f"  [error] {instance_id}: {res.status_code} {res.text}", file=sys.stderr)
            continue
        print(f"  started {instance_id}")
        started.append(instance_id)

    print(
        f"\nstarted {len(started)} / {len(instances)} instances",
        file=sys.stderr,
    )
    return 0


# --- entry point -----------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="swe-studio",
        description="Browse and manage a SWE Studio instance from the terminal.",
    )
    parser.add_argument("--base-url", default=_DEFAULT_BASE, help="Studio API base URL.")
    parser.add_argument("--api-key", default=os.environ.get("SWE_STUDIO_API_KEY"),
                        help="X-API-Key header value for write endpoints.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # runs
    runs_p = sub.add_parser("runs", help="List or inspect runs").add_subparsers(
        dest="subcmd", required=True
    )
    runs_ls = runs_p.add_parser("ls", help="List runs")
    runs_ls.set_defaults(func=cmd_runs_ls)

    # trajectory
    traj = sub.add_parser("traj", help="Inspect a trajectory")
    traj_sub = traj.add_subparsers(dest="subcmd", required=True)
    traj_show = traj_sub.add_parser("show", help="Print a trajectory in plain text")
    traj_show.add_argument("run_id")
    traj_show.add_argument("trajectory_id")
    traj_show.set_defaults(func=cmd_traj_show)

    # search
    s = sub.add_parser("search", help="Full-text search")
    s.add_argument("q")
    s.add_argument("--run-id", default=None)
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(func=cmd_search)

    # summarize
    sm = sub.add_parser("summarize", help="Generate or fetch a trajectory summary")
    sm.add_argument("run_id")
    sm.add_argument("trajectory_id")
    sm.add_argument("--provider", choices=["heuristic", "ai"], default="heuristic")
    sm.add_argument("--force", action="store_true")
    sm.set_defaults(func=cmd_summarize)

    # curate
    curate_p = sub.add_parser("curate", help="Curated trajectory showcase")
    curate_sub = curate_p.add_subparsers(dest="subcmd", required=True)
    c_add = curate_sub.add_parser("add", help="Add a showcase entry")
    c_add.add_argument("--slug", required=True)
    c_add.add_argument("--run-id", required=True)
    c_add.add_argument("--trajectory-id", required=True)
    c_add.add_argument("--title", required=True)
    c_add.add_argument("--description", default=None)
    c_add.add_argument("--step", type=int, default=None)
    c_add.add_argument("--author", default=None)
    c_add.set_defaults(func=cmd_curate_add)
    c_ls = curate_sub.add_parser("ls", help="List showcase entries")
    c_ls.set_defaults(func=cmd_curate_ls)
    c_rm = curate_sub.add_parser("rm", help="Remove a showcase entry")
    c_rm.add_argument("--slug", required=True)
    c_rm.set_defaults(func=cmd_curate_rm)

    # webhook
    hook_p = sub.add_parser("webhook", help="Outgoing webhook subscriptions")
    hook_sub = hook_p.add_subparsers(dest="subcmd", required=True)
    h_ls = hook_sub.add_parser("ls", help="List webhooks")
    h_ls.set_defaults(func=cmd_webhook_ls)
    h_add = hook_sub.add_parser("add", help="Subscribe a URL")
    h_add.add_argument("--url", required=True)
    h_add.add_argument(
        "--events",
        default="",
        help="Comma-separated event names (empty = all). "
        "e.g. trajectory.resolved,summary.generated",
    )
    h_add.add_argument("--description", default=None)
    h_add.set_defaults(func=cmd_webhook_add)
    h_rm = hook_sub.add_parser("rm", help="Delete a webhook by id")
    h_rm.add_argument("--id", required=True, type=int)
    h_rm.set_defaults(func=cmd_webhook_rm)

    # agent
    agent_p = sub.add_parser("agent", help="Launch the in-process coding agent")
    agent_sub = agent_p.add_subparsers(dest="subcmd", required=True)
    a_run = agent_sub.add_parser("run", help="Run the agent against a repository")
    a_run.add_argument("--problem", required=True, help="Problem statement / user task")
    a_run.add_argument("--repo", required=True, help="Path to the working directory")
    a_run.add_argument("--model", default="claude-sonnet-4-5")
    a_run.add_argument("--max-steps", type=int, default=30)
    a_run.add_argument("--max-cost", type=float, default=5.0,
                       help="USD cost ceiling; the loop exits when crossed.")
    a_run.add_argument("--run-id", default=None)
    a_run.add_argument("--trajectory-id", default=None)
    a_run.add_argument("--docker-image", default=None,
                       help="Run bash commands inside this Docker image instead of host subprocess.")
    a_run.set_defaults(func=cmd_agent_run)

    a_ens = agent_sub.add_parser("ensemble", help="Race multiple models on the same problem")
    a_ens.add_argument("--problem", required=True)
    a_ens.add_argument("--repo", required=True)
    a_ens.add_argument("--models", required=True,
                       help="Comma-separated model ids, e.g. claude-sonnet-4-5,gpt-4o-mini")
    a_ens.add_argument("--max-steps", type=int, default=30)
    a_ens.add_argument("--max-cost", type=float, default=5.0)
    a_ens.add_argument("--docker-image", default=None)
    a_ens.set_defaults(func=cmd_agent_ensemble)

    # bench (top-level)
    bench_p = sub.add_parser("bench", help="Batch-run the agent across an instances.jsonl")
    bench_sub = bench_p.add_subparsers(dest="subcmd", required=True)
    b_run = bench_sub.add_parser("run", help="Run the agent over every instance in a JSONL")
    b_run.add_argument("--instances", required=True,
                       help="Path to a .jsonl with instance_id / problem_statement / repo_path per line")
    b_run.add_argument("--model", default="claude-sonnet-4-5")
    b_run.add_argument("--limit", type=int, default=None)
    b_run.add_argument("--max-steps", type=int, default=30)
    b_run.add_argument("--max-cost", type=float, default=5.0)
    b_run.add_argument("--run-id", default=None)
    b_run.add_argument("--docker-image", default=None)
    b_run.set_defaults(func=cmd_bench_run)

    args = parser.parse_args(argv)

    headers: dict[str, str] = {}
    if args.api_key:
        headers["X-API-Key"] = args.api_key

    import httpx  # local import to keep CLI parser fast

    client = StudioClient(base_url=args.base_url)
    client._client.headers.update(headers)
    try:
        return args.func(args, client)
    except httpx.HTTPError as exc:
        print(f"HTTP error: {exc}", file=sys.stderr)
        return 2
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
