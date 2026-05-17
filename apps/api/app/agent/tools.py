"""Built-in agent tools.

Each tool takes a working directory and the args string from the parser, and
returns the observation text plus a `done` flag (set when submit/finish is
called).

Safety guard-rails (subprocess only — no Docker yet):
    * Every shell command times out after `BASH_TIMEOUT` seconds.
    * `read` and `write` paths are resolved relative to the working directory
      and rejected if they escape it.
    * `write` truncates over-large payloads to keep `.traj` files manageable.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

BASH_TIMEOUT = 30
MAX_OBSERVATION = 8_000
MAX_FILE_BYTES = 64_000

TOOL_NAMES: tuple[str, ...] = ("bash", "read", "write", "submit", "finish")


@dataclass
class ToolResult:
    observation: str
    done: bool = False
    submission: str | None = None
    exit_status: str | None = None


def _trim(text: str, limit: int = MAX_OBSERVATION) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 200] + f"\n…[truncated {len(text) - (limit - 200)} chars]"


def _safe_path(workdir: Path, raw: str) -> Path:
    target = (workdir / raw.strip()).resolve()
    if workdir not in target.parents and target != workdir:
        raise ValueError(f"Path escapes the working directory: {raw}")
    return target


def run_tool(
    name: str,
    args: str,
    workdir: Path,
    *,
    docker_image: str | None = None,
) -> ToolResult:
    name = (name or "").lower().strip()
    args = args or ""
    if name == "bash":
        return _bash(args, workdir, docker_image=docker_image)
    if name == "read":
        return _read(args, workdir)
    if name == "write":
        return _write(args, workdir)
    if name == "submit":
        return _submit(args, workdir)
    if name == "finish":
        return ToolResult(
            observation=f"Agent finished without submission.\n{args}".rstrip(),
            done=True,
            exit_status="exit_forfeit",
        )
    return ToolResult(observation=f"Unknown tool '{name}'. Use one of: {', '.join(TOOL_NAMES)}.")


def _bash(args: str, workdir: Path, *, docker_image: str | None = None) -> ToolResult:
    if not args.strip():
        return ToolResult(observation="bash needs a command")
    if docker_image:
        return _bash_docker(args, workdir, docker_image)
    return _bash_subprocess(args, workdir)


def _bash_subprocess(args: str, workdir: Path) -> ToolResult:
    try:
        proc = subprocess.run(
            args,
            shell=True,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=BASH_TIMEOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            observation=f"command timed out after {BASH_TIMEOUT}s: {args}"
        )
    out = (proc.stdout or "") + (proc.stderr or "")
    suffix = "" if proc.returncode == 0 else f"\n[exit {proc.returncode}]"
    return ToolResult(observation=_trim(out.rstrip() + suffix))


def _bash_docker(args: str, workdir: Path, image: str) -> ToolResult:
    """Run `args` inside a throwaway container. The workdir is mounted at
    `/work` and used as the container CWD. Network is disabled by default so
    the agent can't reach outbound services from its sandbox."""
    cmd = [
        "docker", "run", "--rm", "--network=none",
        "-v", f"{workdir}:/work",
        "-w", "/work",
        image,
        "bash", "-lc", args,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=BASH_TIMEOUT + 5,  # docker startup adds a little overhead
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            observation=f"docker command timed out after {BASH_TIMEOUT}s: {args}"
        )
    except FileNotFoundError:
        return ToolResult(
            observation=(
                "docker isn't installed on this server. Either install Docker or "
                "drop the `docker_image` setting to fall back to subprocess."
            )
        )
    out = (proc.stdout or "") + (proc.stderr or "")
    suffix = "" if proc.returncode == 0 else f"\n[exit {proc.returncode}]"
    return ToolResult(observation=_trim(out.rstrip() + suffix))


def _read(args: str, workdir: Path) -> ToolResult:
    path_raw = args.strip().split("\n", 1)[0]
    if not path_raw:
        return ToolResult(observation="read needs a path")
    try:
        path = _safe_path(workdir, path_raw)
    except ValueError as exc:
        return ToolResult(observation=str(exc))
    try:
        data = path.read_bytes()[:MAX_FILE_BYTES]
    except FileNotFoundError:
        return ToolResult(observation=f"file not found: {path_raw}")
    except PermissionError:
        return ToolResult(observation=f"permission denied: {path_raw}")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return ToolResult(observation=f"<binary file: {path_raw}, {len(data)} bytes>")
    return ToolResult(observation=_trim(text))


def _write(args: str, workdir: Path) -> ToolResult:
    """`write <path>\n<content>` — overwrites the file."""
    if "\n" not in args:
        return ToolResult(observation="write needs `<path>\\n<content>`")
    path_raw, content = args.split("\n", 1)
    path_raw = path_raw.strip()
    if not path_raw:
        return ToolResult(observation="write needs a path")
    try:
        path = _safe_path(workdir, path_raw)
    except ValueError as exc:
        return ToolResult(observation=str(exc))
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = content.encode("utf-8")[:MAX_FILE_BYTES]
    path.write_bytes(payload)
    return ToolResult(observation=f"wrote {len(payload)} bytes to {path_raw}")


def _submit(args: str, workdir: Path) -> ToolResult:
    """`submit` — collects `git diff` for the final patch."""
    try:
        proc = subprocess.run(
            ["git", "diff"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=BASH_TIMEOUT,
        )
        diff = proc.stdout or ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        diff = args.strip() or "(no diff available — git not found or timed out)"
    submission = diff.strip() or "(empty diff)"
    return ToolResult(
        observation="Submission collected.\n" + _trim(submission, limit=2_000),
        done=True,
        submission=submission,
        exit_status="submitted",
    )


def shlex_split(args: str) -> list[str]:
    """Convenience for callers that need argv form."""
    return shlex.split(args)
