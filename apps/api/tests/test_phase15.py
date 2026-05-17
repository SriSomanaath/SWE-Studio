from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agent import AgentConfig, run_agent
from app.agent.llm import LLMResult
from app.agent.tools import run_tool


def _stub_chat(scripted: list[str]) -> object:
    it: Iterator[str] = iter(scripted)

    def chat(**_kwargs: object) -> LLMResult:
        try:
            text = next(it)
        except StopIteration:
            text = "THOUGHT: out of script\nACTION: finish"
        return LLMResult(text=text, prompt_tokens=10, completion_tokens=5, cost_usd=0.001)

    return chat


# --- Docker dispatch path --------------------------------------------------


def test_bash_docker_dispatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When `docker_image` is set, the tool layer should invoke docker rather
    than running the command directly on the host."""
    seen: dict[str, object] = {}

    class _FakeProc:
        returncode = 0
        stdout = "container output\n"
        stderr = ""

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        seen["cmd"] = cmd
        return _FakeProc()

    import app.agent.tools as tools_mod

    monkeypatch.setattr(tools_mod.subprocess, "run", fake_run)

    result = run_tool(
        "bash",
        "echo hi",
        tmp_path,
        docker_image="python:3.12-slim",
    )
    assert "container output" in result.observation
    assert seen["cmd"][:4] == ["docker", "run", "--rm", "--network=none"]
    assert "python:3.12-slim" in seen["cmd"]
    assert "/work" in seen["cmd"]


def test_bash_docker_missing_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.agent.tools as tools_mod

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        raise FileNotFoundError("docker")

    monkeypatch.setattr(tools_mod.subprocess, "run", fake_run)
    result = run_tool("bash", "echo hi", tmp_path, docker_image="anything")
    assert "docker isn't installed" in result.observation


# --- Ensemble endpoint -----------------------------------------------------


@pytest.fixture
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("TRAJECTORIES_DIR", str(tmp_path))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "index.sqlite"))
    monkeypatch.setenv("INDEXER_ENABLED", "false")

    from app.config import Settings
    import app.config as config_mod
    import app.trajectory_store as store
    import app.indexer as idx
    import app.db as db_mod
    import app.main as main_mod
    import app.routers.ingest as ingest_mod
    import app.routers.agent as agent_mod
    import app.routers.replay as replay_mod

    config_mod.settings = Settings()
    for m in (store, idx, db_mod, ingest_mod, agent_mod, replay_mod):
        m.settings = config_mod.settings
    store.root_diagnostics.cache_clear()
    db_mod.reset()
    return TestClient(main_mod.app)


def test_ensemble_starts_one_thread_per_model(
    api_client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    started: list[str] = []
    real_thread = __import__("threading").Thread

    class _Capture(real_thread):  # type: ignore[misc, valid-type]
        def __init__(self, *args, **kwargs):  # noqa: ANN001
            started.append(kwargs.get("name", ""))
            super().__init__(*args, **kwargs)
            self._args_captured = args
            self._kwargs_captured = kwargs

        def start(self) -> None:
            return None  # don't actually run the agent in tests

    import app.routers.agent as agent_mod

    monkeypatch.setattr(agent_mod.threading, "Thread", _Capture)

    res = api_client.post(
        "/agent/ensemble",
        json={
            "problem": "fix it",
            "repo": str(repo),
            "models": ["claude-sonnet-4-5", "gpt-4o-mini"],
        },
    )
    assert res.status_code == 202
    body = res.json()
    assert body["run_id"].startswith("ensemble-")
    assert len(body["trajectories"]) == 2
    assert body["compare_url"] is not None
    assert len(started) == 2


def test_ensemble_rejects_empty_models(api_client: TestClient, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    res = api_client.post(
        "/agent/ensemble",
        json={"problem": "x", "repo": str(repo), "models": []},
    )
    assert res.status_code == 400


def test_ensemble_caps_models(api_client: TestClient, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    res = api_client.post(
        "/agent/ensemble",
        json={
            "problem": "x",
            "repo": str(repo),
            "models": ["a", "b", "c", "d", "e", "f", "g"],
        },
    )
    assert res.status_code == 400


# --- Bench harness via the real agent + stub chat --------------------------


def test_bench_two_instances_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Drive `run_agent` directly twice (mimicking the CLI loop) and verify
    Studio ends up with a well-formed multi-trajectory run dir."""
    traj_dir = tmp_path / "trajectories"
    traj_dir.mkdir()

    run_id = "bench-fixture-001"
    chat = _stub_chat(
        [
            # instance one
            "THOUGHT: peek\nACTION: bash ls -1",
            "THOUGHT: done\nACTION: submit",
            # instance two
            "THOUGHT: peek\nACTION: bash ls -1",
            "THOUGHT: done\nACTION: submit",
        ]
    )

    for instance_id in ("inst-a", "inst-b"):
        workdir = tmp_path / f"repo-{instance_id}"
        workdir.mkdir()
        (workdir / "foo.py").write_text("x = 1\n")
        run_agent(
            AgentConfig(
                model="stub/model",
                workdir=workdir,
                problem_statement=f"Solve {instance_id}",
                max_steps=10,
            ),
            run_id=run_id,
            trajectory_id=instance_id,
            trajectories_dir=traj_dir,
            chat_fn=chat,
        )

    run_root = traj_dir / run_id
    files = sorted(p.name for p in run_root.glob("*.traj"))
    assert files == ["inst-a.traj", "inst-b.traj"]
    payload_a = json.loads((run_root / "inst-a.traj").read_text())
    assert payload_a["info"]["exit_status"] == "submitted"
    assert len(payload_a["trajectory"]) == 2
