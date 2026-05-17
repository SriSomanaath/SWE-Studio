"""In-process LLM-driven coding agent.

This is SWE Studio's own agent loop — the side that produces `.traj` files.
The rest of Studio is the consumer side (indexer, viewer, analytics). Putting
both in the same package closes the loop: Studio can now solve a problem
*and* render the solving process.

Design notes:
    * Tiny tool surface (bash, read, write, submit, finish) inspired by
      a typical coding-agent tool registry but written from scratch so we don't take a
      runtime dependency on it.
    * Parser uses plain `THOUGHT: …\\nACTION: <tool> <args>` rather than the
      JSON tool-use schema, which keeps it provider-agnostic and easy to
      debug. Implementations can still swap in native tool-calling later.
    * Trajectory writes are atomic + incremental, so Phase 3 live mode picks
      up the in-progress run with no extra plumbing.
"""

from .runner import AgentConfig, AgentResult, run_agent
from .tools import TOOL_NAMES

__all__ = ["AgentConfig", "AgentResult", "run_agent", "TOOL_NAMES"]
