"""The agent loop.

Single entry point :func:`run_agent` that takes a config, drives a
think→act→observe cycle, and writes an incremental `.traj` file compatible
with the rest of SWE Studio's tooling. Designed to be invokable from a
FastAPI background task, a CLI, or a test fixture.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import llm as llm_module
from . import tools as tools_module
from .protocol import parse

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are an autonomous coding agent embedded in SWE Studio.

Solve the task by calling the provided tools, exactly one per turn. Before
each call, write 1-3 sentences of reasoning.

    bash     run a shell command in the repository root (30 s timeout):
             grep, ls, cat, run tests, apply sed patches, ...
    read     print a file
    write    overwrite a file with new content
    submit   you are done: the current `git diff` becomes your patch
    finish   give up without a patch

Explore before you patch, prefer small reversible commands, and call submit
once the task is solved.

If tools are unavailable, reply instead with exactly two lines:
    THOUGHT: <reasoning>
    ACTION: <tool> <args>     (for write: path on this line, content below)
"""


@dataclass
class AgentConfig:
    model: str = "claude-sonnet-4-5"
    api_key: str | None = None
    max_steps: int = 30
    max_cost_usd: float = 5.0
    workdir: Path = Path(".")
    problem_statement: str = ""
    system_prompt: str = SYSTEM_PROMPT
    # When set, `bash` commands run inside `docker run --rm --network=none …`
    # against the named image. Falls back to subprocess otherwise.
    docker_image: str | None = None


@dataclass
class AgentResult:
    run_id: str
    trajectory_id: str
    file_path: Path
    step_count: int
    exit_status: str
    instance_cost: float
    tokens_sent: int
    tokens_received: int
    tokens_cached: int = 0


@dataclass
class _Step:
    thought: str
    action: str
    response: str
    observation: str
    messages: list[dict[str, Any]] = field(default_factory=list)


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload))
    tmp.replace(path)


def _build_payload(
    *,
    config: AgentConfig,
    history: list[dict[str, Any]],
    steps: list[_Step],
    exit_status: str,
    submission: str | None,
    cost: float,
    tokens_in: int,
    tokens_out: int,
    api_calls: int,
    tokens_cached: int = 0,
) -> dict[str, Any]:
    return {
        "history": history,
        "trajectory": [
            {
                "thought": s.thought,
                "action": s.action,
                "response": s.response,
                "observation": s.observation,
                "messages": s.messages,
            }
            for s in steps
        ],
        "info": {
            # Lets /ingest label metrics by model (app/observability.py).
            "model": config.model,
            "exit_status": exit_status,
            "submission": submission,
            "model_stats": {
                "instance_cost": cost,
                "tokens_sent": tokens_in,
                "tokens_received": tokens_out,
                "tokens_cached": tokens_cached,
                "api_calls": api_calls,
            },
        },
    }


def run_agent(
    config: AgentConfig,
    *,
    run_id: str,
    trajectory_id: str,
    trajectories_dir: Path,
    chat_fn: Callable[..., llm_module.LLMResult] | None = None,
) -> AgentResult:
    """Drive the loop to completion and return its summary.

    ``chat_fn`` is injectable so tests can substitute a deterministic stub
    without depending on litellm or a real API key.
    """
    chat = chat_fn or llm_module.chat

    run_dir = (trajectories_dir / run_id).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    traj_path = run_dir / f"{trajectory_id}.traj"

    history: list[dict[str, Any]] = [
        {"role": "system", "content": config.system_prompt},
        {"role": "user", "content": config.problem_statement or "Investigate the repository and submit a useful patch."},
    ]
    steps: list[_Step] = []
    exit_status = "running"
    submission: str | None = None
    cost = 0.0
    tokens_in = 0
    tokens_out = 0
    tokens_cached = 0
    api_calls = 0

    # Write the initial "running" payload so live mode lights up immediately.
    _atomic_write(
        traj_path,
        _build_payload(
            config=config,
            history=history,
            steps=steps,
            exit_status=exit_status,
            submission=submission,
            cost=cost,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            api_calls=api_calls,
            tokens_cached=tokens_cached,
        ),
    )

    for step_idx in range(config.max_steps):
        if cost >= config.max_cost_usd:
            exit_status = "exit_cost"
            steps.append(_Step(thought="", action="", response="", observation=f"Hit cost cap ${cost:.2f}"))
            break

        try:
            llm_result = chat(
                messages=history,
                model=config.model,
                api_key=config.api_key,
                tools=tools_module.TOOL_SCHEMAS,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("LLM call failed at step %d", step_idx)
            exit_status = "exit_error"
            steps.append(_Step(thought="", action="", response="", observation=f"LLM error: {exc}"))
            break

        api_calls += 1
        cost += llm_result.cost_usd
        tokens_in += llm_result.prompt_tokens
        tokens_out += llm_result.completion_tokens
        tokens_cached += llm_result.cached_tokens

        text = llm_result.text
        if llm_result.tool_calls:
            assistant: dict[str, Any] = {
                "role": "assistant",
                "content": text or None,
                "tool_calls": [
                    {"id": c["id"], "type": "function",
                     "function": {"name": c["name"], "arguments": c["arguments"]}}
                    for c in llm_result.tool_calls
                ],
            }
            if llm_result.reasoning:
                assistant["reasoning_content"] = llm_result.reasoning
            history.append(assistant)
            actions = [(c["id"], *tools_module.from_call(c["name"], c["arguments"]))
                       for c in llm_result.tool_calls]
            thought = text.strip()
            response = "\n".join([text, *(f"{c['name']}({c['arguments']})" for c in llm_result.tool_calls)]).strip()
        else:
            # Text fallback for models/servers without tool calling.
            parsed = parse(text)
            history.append({"role": "assistant", "content": text})
            actions = [(None, parsed.tool, parsed.args)]
            thought, response = parsed.thought, parsed.raw

        done: tools_module.ToolResult | None = None
        for call_id, tool, args in actions:
            result = tools_module.run_tool(tool, args, config.workdir, docker_image=config.docker_image)
            # Every tool call needs its own result message (APIs reject
            # unanswered tool_use blocks); text turns get a user OBSERVATION.
            history.append(
                {"role": "tool", "tool_call_id": call_id, "content": result.observation}
                if call_id
                else {"role": "user", "content": f"OBSERVATION:\n{result.observation}"}
            )
            steps.append(_Step(thought=thought, action=f"{tool} {args}".rstrip(),
                               response=response, observation=result.observation))
            if result.submission is not None:
                submission = result.submission
            if result.done:
                done = result
                break

        _atomic_write(
            traj_path,
            _build_payload(
                config=config,
                history=history,
                steps=steps,
                exit_status="running",
                submission=submission,
                cost=cost,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                api_calls=api_calls,
                tokens_cached=tokens_cached,
            ),
        )

        if done:
            exit_status = done.exit_status or "submitted"
            break
    else:
        exit_status = "exit_step_limit"

    _atomic_write(
        traj_path,
        _build_payload(
            config=config,
            history=history,
            steps=steps,
            exit_status=exit_status,
            submission=submission,
            cost=cost,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            api_calls=api_calls,
            tokens_cached=tokens_cached,
        ),
    )

    return AgentResult(
        run_id=run_id,
        trajectory_id=trajectory_id,
        file_path=traj_path,
        step_count=len(steps),
        exit_status=exit_status,
        instance_cost=cost,
        tokens_sent=tokens_in,
        tokens_received=tokens_out,
        tokens_cached=tokens_cached,
    )
