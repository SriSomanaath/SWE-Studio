from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _write_traj(path: Path, *, exit_status: str, cost: float, steps: int, tokens_sent: int) -> None:
    payload = {
        "history": [
            {"role": "system", "content": "You are a software engineer."},
            {"role": "user", "content": f"Fix {path.stem}"},
        ],
        "trajectory": [
            {
                "thought": f"step {i}",
                "action": f"echo step {i}",
                "response": "",
                "observation": f"out {i}",
                "messages": [],
            }
            for i in range(steps)
        ],
        "info": {
            "exit_status": exit_status,
            "submission": "diff --git a/x b/x\n" if exit_status == "submitted" else None,
            "model_stats": {
                "instance_cost": cost,
                "tokens_sent": tokens_sent,
                "tokens_received": tokens_sent // 4,
                "api_calls": steps,
            },
        },
    }
    path.write_text(json.dumps(payload))


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    run_dir = tmp_path / "run-A"
    run_dir.mkdir()

    _write_traj(run_dir / "alpha.traj", exit_status="submitted", cost=0.10, steps=4, tokens_sent=2000)
    _write_traj(run_dir / "beta.traj", exit_status="exit_forfeit", cost=0.55, steps=12, tokens_sent=18000)
    _write_traj(run_dir / "gamma.traj", exit_status="submitted", cost=0.22, steps=7, tokens_sent=5000)

    (run_dir / "results.json").write_text(
        json.dumps(
            {
                "completed_ids": ["alpha", "beta", "gamma"],
                "submitted_ids": ["alpha", "gamma"],
                "resolved_ids": ["alpha"],
            }
        )
    )

    monkeypatch.setenv("TRAJECTORIES_DIR", str(tmp_path))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "index.sqlite"))
    monkeypatch.setenv("INDEXER_ENABLED", "false")  # disable filesystem watcher in tests

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


def test_health(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["trajectories_dir_exists"] is True


def test_list_runs(client: TestClient) -> None:
    res = client.get("/runs")
    assert res.status_code == 200
    runs = res.json()
    assert len(runs) == 1
    r = runs[0]
    assert r["id"] == "run-A"
    assert r["trajectory_count"] == 3
    assert r["resolved_count"] == 1
    assert r["submitted_count"] == 2


def test_filter_resolved_only(client: TestClient) -> None:
    res = client.get("/runs/run-A/trajectories", params={"status": "resolved"})
    assert res.status_code == 200
    body = res.json()
    assert [t["id"] for t in body] == ["alpha"]
    assert res.headers["X-Total-Count"] == "1"


def test_filter_failed(client: TestClient) -> None:
    res = client.get("/runs/run-A/trajectories", params={"status": "failed"})
    assert res.status_code == 200
    ids = {t["id"] for t in res.json()}
    assert ids == {"beta", "gamma"}  # completed but not resolved


def test_filter_exit_substring(client: TestClient) -> None:
    res = client.get("/runs/run-A/trajectories", params={"exit": "forfeit"})
    assert [t["id"] for t in res.json()] == ["beta"]


def test_filter_cost_range(client: TestClient) -> None:
    res = client.get("/runs/run-A/trajectories", params={"cost_min": 0.2, "cost_max": 0.5})
    assert [t["id"] for t in res.json()] == ["gamma"]


def test_search(client: TestClient) -> None:
    res = client.get("/runs/run-A/trajectories", params={"search": "alpha"})
    assert [t["id"] for t in res.json()] == ["alpha"]


def test_sort_by_cost_desc(client: TestClient) -> None:
    res = client.get(
        "/runs/run-A/trajectories",
        params={"sort": "instance_cost", "order": "desc"},
    )
    assert [t["id"] for t in res.json()] == ["beta", "gamma", "alpha"]


def test_pagination(client: TestClient) -> None:
    res = client.get("/runs/run-A/trajectories", params={"limit": 2, "offset": 0})
    assert len(res.json()) == 2
    assert res.headers["X-Total-Count"] == "3"


def test_stats(client: TestClient) -> None:
    res = client.get("/runs/run-A/stats")
    assert res.status_code == 200
    s = res.json()
    assert s["trajectory_count"] == 3
    assert s["resolved_count"] == 1
    assert s["completed_count"] == 3
    assert s["pass_rate"] == pytest.approx(1 / 3)
    assert s["total_cost"] == pytest.approx(0.87)
    assert s["total_api_calls"] == 23
    assert s["median_step_count"] == 7
    assert s["exit_status_counts"] == {"submitted": 2, "exit_forfeit": 1}


def test_trajectory_detail(client: TestClient) -> None:
    res = client.get("/runs/run-A/trajectories/alpha")
    assert res.status_code == 200
    detail = res.json()
    assert detail["problem_statement"] == "Fix alpha"
    assert len(detail["steps"]) == 4
    assert detail["eval"]["resolved"] is True


def test_trajectory_not_found(client: TestClient) -> None:
    assert client.get("/runs/run-A/trajectories/nope").status_code == 404


def test_indexer_picks_up_new_file(client: TestClient, tmp_path: Path) -> None:
    new_path = tmp_path / "run-A" / "delta.traj"
    _write_traj(new_path, exit_status="submitted", cost=0.05, steps=2, tokens_sent=800)

    import app.indexer as idx

    idx.bulk_reindex()
    res = client.get("/runs/run-A/trajectories")
    ids = {t["id"] for t in res.json()}
    assert "delta" in ids


def test_indexer_drops_deleted_file(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "run-A" / "beta.traj").unlink()
    import app.indexer as idx

    idx.bulk_reindex()
    res = client.get("/runs/run-A/trajectories")
    ids = {t["id"] for t in res.json()}
    assert "beta" not in ids
