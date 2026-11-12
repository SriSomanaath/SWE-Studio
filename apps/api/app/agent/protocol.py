"""Parse the LLM's free-text response into `(thought, tool, args)`.

We expect the model to follow this format::

    THOUGHT: ...one or many lines...
    ACTION: <tool> <args>

`args` may span multiple lines for the `write` tool. The parser tolerates
extra whitespace, surrounding code fences, and missing THOUGHT.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_FENCE_RE = re.compile(r"^```[a-zA-Z0-9_-]*\n|\n```$")
_THOUGHT_RE = re.compile(r"^THOUGHT:\s*", re.IGNORECASE | re.MULTILINE)
_ACTION_RE = re.compile(r"^ACTION:\s*", re.IGNORECASE | re.MULTILINE)


@dataclass
class ParsedAction:
    thought: str
    tool: str
    args: str
    raw: str


def parse(response: str) -> ParsedAction:
    text = _FENCE_RE.sub("", response.strip())

    action_match = _ACTION_RE.search(text)
    if not action_match:
        # No ACTION line: a format slip, not a decision to give up (Kimi K3
        # does this on step 1). An empty tool makes run_tool reply with a
        # format reminder so the model retries; max_steps bounds the loop.
        return ParsedAction(
            thought=_THOUGHT_RE.sub("", text, count=1).strip(), tool="", args="", raw=response
        )

    before = text[: action_match.start()]
    after = text[action_match.end() :]

    thought_match = _THOUGHT_RE.search(before)
    thought = before[thought_match.end() :].strip() if thought_match else before.strip()

    # `after` is everything past the literal "ACTION:" marker. The first
    # line is the tool + its inline arg; everything after the first newline
    # is the body (used by `write`). We preserve trailing newlines in the
    # body so file writes round-trip exactly.
    after_clean = after.lstrip("\n")
    head, _, body = after_clean.partition("\n")
    head = head.strip()

    tool, _, head_args = head.partition(" ")
    tool = tool.lower().strip() or "finish"
    inline_args = head_args.strip()

    args = (f"{inline_args}\n{body}" if inline_args else body) if body else inline_args

    return ParsedAction(thought=thought, tool=tool, args=args, raw=response)
