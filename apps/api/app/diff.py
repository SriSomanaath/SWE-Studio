"""Minimal unified-diff parser for agent submissions.

Just enough to compute file-level deltas (added/removed line counts per file)
without pulling in `unidiff`. Tolerates the loose subset of unified diff that
the agent's `submission` field uses.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FileDiff:
    path: str
    added: int = 0
    removed: int = 0


def parse_unified_diff(diff: str | None) -> dict[str, FileDiff]:
    """Return {path: FileDiff} keyed by the new-path (post-image)."""
    if not diff:
        return {}

    files: dict[str, FileDiff] = {}
    current: FileDiff | None = None

    for raw_line in diff.splitlines():
        if raw_line.startswith("diff --git "):
            current = None
            continue
        if raw_line.startswith("+++ "):
            path = raw_line[4:].strip()
            # Strip leading "b/" if present (git-style).
            if path.startswith("b/"):
                path = path[2:]
            if path == "/dev/null":
                continue
            current = files.setdefault(path, FileDiff(path=path))
            continue
        if raw_line.startswith("--- "):
            # We pick up the new path on `+++`; only worth handling here when
            # the diff is one-sided (--- only, no +++).
            continue
        if current is None:
            continue
        # Skip hunk headers.
        if raw_line.startswith("@@"):
            continue
        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            current.added += 1
        elif raw_line.startswith("-") and not raw_line.startswith("---"):
            current.removed += 1

    return files


@dataclass
class DiffMerge:
    paths_a: set[str] = field(default_factory=set)
    paths_b: set[str] = field(default_factory=set)
    in_both: set[str] = field(default_factory=set)
    only_a: set[str] = field(default_factory=set)
    only_b: set[str] = field(default_factory=set)


def merge(a: dict[str, FileDiff], b: dict[str, FileDiff]) -> DiffMerge:
    pa, pb = set(a), set(b)
    return DiffMerge(
        paths_a=pa,
        paths_b=pb,
        in_both=pa & pb,
        only_a=pa - pb,
        only_b=pb - pa,
    )
