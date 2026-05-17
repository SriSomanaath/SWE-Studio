"""Curate a trajectory into the SWE Studio showcase.

Usage::

    python -m app.tools.curate add \\
        --slug django-boolean-fix \\
        --run sample-run-001 \\
        --traj django__django-12345 \\
        --title "BooleanField accepts integer 0 and 1" \\
        --description "Two-line patch landed by the agent in 7 steps." \\
        --step 3

    python -m app.tools.curate list
    python -m app.tools.curate delete --slug django-boolean-fix

The CLI talks to the local API over HTTP so it works the same way against a
running dev server or a Docker-deployed instance.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any


def _request(
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    author: str | None = None,
) -> tuple[int, dict[str, Any] | None]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if author:
        headers["X-Author"] = author
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            text = resp.read().decode()
            return resp.status, json.loads(text) if text else None
    except urllib.error.HTTPError as exc:
        text = exc.read().decode(errors="replace")
        try:
            return exc.code, json.loads(text)
        except json.JSONDecodeError:
            return exc.code, {"detail": text}


def _print_entry(entry: dict[str, Any]) -> None:
    print(f"  {entry['slug']:32}  {entry['run_id']}:{entry['trajectory_id']}  — {entry['title']}")


def cmd_add(args: argparse.Namespace) -> int:
    payload = {
        "slug": args.slug,
        "run_id": args.run,
        "trajectory_id": args.traj,
        "title": args.title,
        "description": args.description,
        "pinned_step": args.step,
    }
    status, body = _request(
        "POST",
        f"{args.base_url}/showcase",
        body=payload,
        author=args.author,
    )
    if status == 201 and body:
        print(f"created {args.base_url}/showcase/{body['slug']}", file=sys.stderr)
        return 0
    print(f"error {status}: {body}", file=sys.stderr)
    return 1


def cmd_list(args: argparse.Namespace) -> int:
    status, body = _request("GET", f"{args.base_url}/showcase")
    if status != 200 or not isinstance(body, list):
        print(f"error {status}: {body}", file=sys.stderr)
        return 1
    if not body:
        print("(no showcase entries)")
        return 0
    for entry in body:
        _print_entry(entry)
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    status, body = _request("DELETE", f"{args.base_url}/showcase/{args.slug}")
    if status in (200, 204):
        print(f"deleted {args.slug}", file=sys.stderr)
        return 0
    print(f"error {status}: {body}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8080",
        help="SWE Studio API base URL (default: http://127.0.0.1:8080).",
    )
    parser.add_argument("--author", default=None, help="Author display name (X-Author header).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Add a showcase entry.")
    p_add.add_argument("--slug", required=True)
    p_add.add_argument("--run", required=True, help="Run id.")
    p_add.add_argument("--traj", required=True, help="Trajectory id.")
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--description", default=None)
    p_add.add_argument("--step", type=int, default=None, help="0-indexed pinned step.")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="List showcase entries.")
    p_list.set_defaults(func=cmd_list)

    p_del = sub.add_parser("delete", help="Delete a showcase entry by slug.")
    p_del.add_argument("--slug", required=True)
    p_del.set_defaults(func=cmd_delete)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
