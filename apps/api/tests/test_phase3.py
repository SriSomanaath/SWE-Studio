from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.streaming import EventBus
from app.tools import replay


def _write_traj(path: Path, steps: int, *, exit_status: str = "submitted") -> None:
    payload = {
        "history": [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": f"Fix {path.stem}"},
        ],
        "trajectory": [
            {"thought": f"t{i}", "action": f"echo {i}", "response": "", "observation": f"o{i}", "messages": []}
            for i in range(steps)
        ],
        "info": {
            "exit_status": exit_status,
            "submission": "diff --git a/x b/x\n",
            "model_stats": {
                "instance_cost": 0.1 * (steps + 1),
                "tokens_sent": 1000 * steps,
                "tokens_received": 250 * steps,
                "api_calls": steps,
            },
        },
    }
    path.write_text(json.dumps(payload))


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    run_dir = tmp_path / "run-X"
    run_dir.mkdir()
    _write_traj(run_dir / "alpha.traj", steps=4)
    _write_traj(run_dir / "beta.traj", steps=8, exit_status="exit_forfeit")
    (run_dir / "results.json").write_text(
        json.dumps(
            {
                "completed_ids": ["alpha", "beta"],
                "submitted_ids": ["alpha"],
                "resolved_ids": ["alpha"],
            }
        )
    )

    monkeypatch.setenv("TRAJECTORIES_DIR", str(tmp_path))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "index.sqlite"))
    monkeypatch.setenv("INDEXER_ENABLED", "false")

    import app.config as config_mod
    import app.db as db_mod
    import app.indexer as idx
    import app.main as main_mod
    import app.trajectory_store as store
    from app.config import Settings

    config_mod.settings = Settings()
    store.settings = config_mod.settings
    idx.settings = config_mod.settings
    db_mod.settings = config_mod.settings

    store.root_diagnostics.cache_clear()
    db_mod.reset()
    idx.bulk_reindex()

    return TestClient(main_mod.app)


def test_live_endpoint_window(client: TestClient, tmp_path: Path) -> None:
    # Force the alpha trajectory mtime into the past so it falls outside the window.
    old = time.time() - 3600
    (tmp_path / "run-X" / "alpha.traj").touch()
    import os
    os.utime(tmp_path / "run-X" / "alpha.traj", (old, old))

    import app.indexer as idx
    idx.bulk_reindex()

    res = client.get("/live", params={"since": 60})
    ids = [t["trajectory_id"] for t in res.json()]
    assert "alpha" not in ids
    assert "beta" in ids


def test_compare_endpoint(client: TestClient) -> None:
    res = client.get("/compare", params={"a": "run-X:alpha", "b": "run-X:beta"})
    assert res.status_code == 200
    body = res.json()
    assert body["a"]["id"] == "alpha"
    assert body["b"]["id"] == "beta"
    s = body["summary"]
    assert s["step_count_a"] == 4
    assert s["step_count_b"] == 8
    assert s["step_count_delta"] == 4
    assert s["eval_resolved_a"] is True
    assert s["eval_resolved_b"] is False
    # alpha actions are "echo 0..3", beta "echo 0..7" => overlap = 4 / 8
    assert s["action_overlap_ratio"] == pytest.approx(0.5)


def test_compare_bad_ref(client: TestClient) -> None:
    assert client.get("/compare", params={"a": "no-colon", "b": "run-X:alpha"}).status_code == 400


@pytest.mark.asyncio
async def test_event_bus_basic() -> None:
    eb = EventBus()
    eb.bind_loop(asyncio.get_running_loop())
    received: list[dict] = []

    async def consumer() -> None:
        async for evt in eb.stream("t"):
            received.append(evt)
            if len(received) == 2:
                return

    task = asyncio.create_task(consumer())
    await asyncio.sleep(0)  # let consumer subscribe
    eb.publish("t", {"type": "a"})
    eb.publish("t", {"type": "b"})
    await asyncio.wait_for(task, timeout=1.0)
    assert [e["type"] for e in received] == ["a", "b"]


def test_replay_writes_incremental_files(tmp_path: Path) -> None:
    src = tmp_path / "src.traj"
    _write_traj(src, steps=3)

    dst = tmp_path / "dst.traj"
    replay.replay(src, dst, delay=0.0)

    assert dst.exists()
    final = json.loads(dst.read_text())
    assert final["info"]["exit_status"] == "submitted"
    assert len(final["trajectory"]) == 3


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


pytest_plugins = ["pytest_asyncio"]
