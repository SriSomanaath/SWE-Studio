from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.agent import AgentConfig, run_agent
from app.agent.llm import LLMResult
from app.agent.protocol import parse


# --- protocol -------------------------------------------------------------


def test_parse_basic() -> None:
    p = parse("THOUGHT: explore\nACTION: bash ls -la")
    assert p.thought == "explore"
    assert p.tool == "bash"
    assert p.args == "ls -la"


def test_parse_multiline_write() -> None:
    p = parse(
        "THOUGHT: rewrite foo.py\nACTION: write foo.py\n"
        "def foo():\n    return 2\n"
    )
    assert p.tool == "write"
    assert p.args.startswith("foo.py\n")
    assert "return 2" in p.args


def test_parse_missing_action_finishes() -> None:
    p = parse("Just rambling without an ACTION line.")
    assert p.tool == "finish"


def test_parse_strips_code_fence() -> None:
    p = parse("```\nTHOUGHT: x\nACTION: bash echo hi\n```")
    assert p.tool == "bash"
    assert p.args == "echo hi"


# --- runner end-to-end with stub LLM --------------------------------------


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "foo.py").write_text("x = 1\n")
    return repo


@pytest.fixture
def traj_dir(tmp_path: Path) -> Path:
    out = tmp_path / "trajectories"
    out.mkdir()
    return out


def _stub_chat_factory(scripted: list[str]) -> object:
    """Returns a callable matching `llm.chat`'s signature that yields the
    next scripted assistant message each call."""
    it: Iterator[str] = iter(scripted)

    def chat(**_kwargs: object) -> LLMResult:
        try:
            text = next(it)
        except StopIteration:
            text = "THOUGHT: out of script\nACTION: finish"
        return LLMResult(text=text, prompt_tokens=10, completion_tokens=5, cost_usd=0.001)

    return chat


def test_agent_completes_submit_flow(workdir: Path, traj_dir: Path) -> None:
    chat = _stub_chat_factory(
        [
            "THOUGHT: list files\nACTION: bash ls -1",
            "THOUGHT: read foo\nACTION: read foo.py",
            "THOUGHT: patch foo\nACTION: write foo.py\nx = 2\n",
            "THOUGHT: done\nACTION: submit",
        ]
    )
    result = run_agent(
        AgentConfig(
            model="stub/model",
            workdir=workdir,
            problem_statement="Change x to 2",
            max_steps=10,
        ),
        run_id="agent-test",
        trajectory_id="t1",
        trajectories_dir=traj_dir,
        chat_fn=chat,
    )

    assert result.step_count == 4
    assert result.exit_status == "submitted"
    assert result.instance_cost == pytest.approx(0.004)
    # The trailing newline in the LLM's response is "end of message",
    # not file content — so the written file ends at "x = 2".
    assert (workdir / "foo.py").read_text() == "x = 2"

    payload = json.loads(result.file_path.read_text())
    assert payload["info"]["exit_status"] == "submitted"
    assert len(payload["trajectory"]) == 4
    assert payload["trajectory"][0]["action"].startswith("bash ")
    assert payload["info"]["model_stats"]["api_calls"] == 4


def test_agent_step_limit(workdir: Path, traj_dir: Path) -> None:
    chat = _stub_chat_factory(["THOUGHT: spin\nACTION: bash echo hi"] * 50)
    result = run_agent(
        AgentConfig(
            model="stub/model",
            workdir=workdir,
            problem_statement="never finish",
            max_steps=3,
        ),
        run_id="agent-test",
        trajectory_id="capped",
        trajectories_dir=traj_dir,
        chat_fn=chat,
    )
    assert result.step_count == 3
    assert result.exit_status == "exit_step_limit"


def test_agent_cost_cap(workdir: Path, traj_dir: Path) -> None:
    # Each call costs $0.001 (stub). Cap at $0.0015 — should stop after 2.
    chat = _stub_chat_factory(["THOUGHT: spin\nACTION: bash echo hi"] * 20)
    result = run_agent(
        AgentConfig(
            model="stub/model",
            workdir=workdir,
            problem_statement="watch cost",
            max_steps=20,
            max_cost_usd=0.0015,
        ),
        run_id="agent-test",
        trajectory_id="capped-cost",
        trajectories_dir=traj_dir,
        chat_fn=chat,
    )
    assert result.exit_status == "exit_cost"
    assert result.step_count <= 4


def test_agent_handles_tool_errors(workdir: Path, traj_dir: Path) -> None:
    chat = _stub_chat_factory(
        [
            # Bad write payload (no body) → tool returns error observation.
            "THOUGHT: bad write\nACTION: write",
            # Recover, finish.
            "THOUGHT: give up\nACTION: finish",
        ]
    )
    result = run_agent(
        AgentConfig(
            model="stub/model",
            workdir=workdir,
            problem_statement="trip an error",
            max_steps=5,
        ),
        run_id="agent-test",
        trajectory_id="errs",
        trajectories_dir=traj_dir,
        chat_fn=chat,
    )
    payload = json.loads(result.file_path.read_text())
    first_obs = payload["trajectory"][0]["observation"]
    assert "write needs" in first_obs


def test_agent_incremental_writes(workdir: Path, traj_dir: Path) -> None:
    chat = _stub_chat_factory(
        [
            "THOUGHT: step 1\nACTION: bash echo one",
            "THOUGHT: step 2\nACTION: bash echo two",
            "THOUGHT: done\nACTION: submit",
        ]
    )
    # Snapshot the file mid-flight to confirm partial writes are well-formed.
    seen_running = False
    original = run_agent.__globals__["_atomic_write"]  # type: ignore[attr-defined]

    captured: list[int] = []

    def wrapping_write(path: Path, payload: dict) -> None:
        captured.append(len(payload["trajectory"]))
        nonlocal seen_running
        if payload["info"]["exit_status"] == "running":
            seen_running = True
        original(path, payload)

    run_agent.__globals__["_atomic_write"] = wrapping_write  # type: ignore[attr-defined]
    try:
        run_agent(
            AgentConfig(
                model="stub/model",
                workdir=workdir,
                problem_statement="watch increments",
                max_steps=10,
            ),
            run_id="agent-test",
            trajectory_id="streamy",
            trajectories_dir=traj_dir,
            chat_fn=chat,
        )
    finally:
        run_agent.__globals__["_atomic_write"] = original  # type: ignore[attr-defined]

    # Initial write (0 steps) + 3 step writes + 1 final write = 5
    assert captured[0] == 0
    assert seen_running is True
    assert captured[-1] == 3
