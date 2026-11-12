from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _write_traj(
    path: Path,
    *,
    exit_status: str,
    cost: float,
    steps: int,
) -> None:
    payload = {
        "history": [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": f"Fix {path.stem}"},
        ],
        "trajectory": [
            {
                "thought": f"t{i}",
                "action": f"echo {i}",
                "response": "",
                "observation": "",
                "messages": [],
            }
            for i in range(steps)
        ],
        "info": {
            "exit_status": exit_status,
            "submission": None,
            "model_stats": {
                "instance_cost": cost,
                "tokens_sent": 1000 * steps,
                "tokens_received": 250 * steps,
                "api_calls": steps,
            },
        },
    }
    path.write_text(json.dumps(payload))


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Run A — cheap & mostly resolved.
    run_a = tmp_path / "run-a"
    run_a.mkdir()
    _write_traj(run_a / "inst-1.traj", exit_status="submitted", cost=0.03, steps=3)
    _write_traj(run_a / "inst-2.traj", exit_status="submitted", cost=0.08, steps=6)
    _write_traj(run_a / "inst-3.traj", exit_status="exit_forfeit", cost=0.55, steps=22)
    _write_traj(run_a / "inst-only-a.traj", exit_status="submitted", cost=0.30, steps=15)
    (run_a / "results.json").write_text(
        json.dumps(
            {
                "completed_ids": ["inst-1", "inst-2", "inst-3", "inst-only-a"],
                "submitted_ids": ["inst-1", "inst-2", "inst-only-a"],
                "resolved_ids": ["inst-1", "inst-2", "inst-only-a"],
            }
        )
    )

    # Run B — expensive & less resolved; diverges on inst-2 and inst-3.
    run_b = tmp_path / "run-b"
    run_b.mkdir()
    _write_traj(run_b / "inst-1.traj", exit_status="submitted", cost=0.07, steps=4)
    _write_traj(run_b / "inst-2.traj", exit_status="exit_forfeit", cost=0.15, steps=11)
    _write_traj(run_b / "inst-3.traj", exit_status="submitted", cost=0.40, steps=18)
    _write_traj(run_b / "inst-only-b.traj", exit_status="exit_forfeit", cost=1.20, steps=45)
    (run_b / "results.json").write_text(
        json.dumps(
            {
                "completed_ids": ["inst-1", "inst-2", "inst-3", "inst-only-b"],
                "submitted_ids": ["inst-1", "inst-3"],
                "resolved_ids": ["inst-1", "inst-3"],
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


def test_analytics_shape(client: TestClient) -> None:
    res = client.get("/runs/run-a/analytics")
    assert res.status_code == 200
    a = res.json()
    # Cost buckets present in order, with right total.
    labels = [b["label"] for b in a["cost_histogram"]]
    assert labels == [
        "$0.00–0.05",
        "$0.05–0.10",
        "$0.10–0.25",
        "$0.25–0.50",
        "$0.50–1.00",
        "$1.00+",
    ]
    counts = {b["label"]: b["count"] for b in a["cost_histogram"]}
    # inst-1=0.03, inst-2=0.08, inst-only-a=0.30, inst-3=0.55
    assert counts["$0.00–0.05"] == 1
    assert counts["$0.05–0.10"] == 1
    assert counts["$0.25–0.50"] == 1
    assert counts["$0.50–1.00"] == 1


def test_analytics_pass_rate_by_step_bucket(client: TestClient) -> None:
    a = client.get("/runs/run-a/analytics").json()
    by_bucket = {b["label"]: b for b in a["pass_rate_by_step_bucket"]}
    # inst-1=3 steps → 1–5 bucket, resolved
    assert by_bucket["1–5"]["resolved"] == 1
    assert by_bucket["1–5"]["total"] == 1
    # inst-2=6 → 6–10, inst-only-a=15 → 11–20 resolved; inst-3=22 → 21–40 not resolved
    assert by_bucket["21–40"]["resolved"] == 0
    assert by_bucket["21–40"]["total"] == 1


def test_analytics_top_costly_order(client: TestClient) -> None:
    a = client.get("/runs/run-a/analytics").json()
    costs = [t["instance_cost"] for t in a["top_costly"]]
    assert costs == sorted(costs, reverse=True)
    assert a["top_costly"][0]["id"] == "inst-3"


def test_runs_compare_summary(client: TestClient) -> None:
    res = client.get("/runs/compare", params={"a": "run-a", "b": "run-b"})
    assert res.status_code == 200
    body = res.json()
    s = body["summary"]
    assert s["instances_in_both"] == 3
    assert s["instances_in_a_only"] == 1  # inst-only-a
    assert s["instances_in_b_only"] == 1  # inst-only-b
    # divergent: inst-2 (resolved in A, not in B), inst-3 (not in A, resolved in B),
    # inst-only-a (resolved in A, absent in B), inst-only-b (failed in B, absent in A)
    assert s["resolved_in_both"] == 1  # inst-1
    assert s["resolved_only_a"] >= 1  # inst-2
    assert s["resolved_only_b"] >= 1  # inst-3
    assert s["cost_delta"] == pytest.approx(s["total_cost_b"] - s["total_cost_a"])


def test_runs_compare_instance_rows(client: TestClient) -> None:
    body = client.get("/runs/compare", params={"a": "run-a", "b": "run-b"}).json()
    rows = {r["id"]: r for r in body["instances"]}

    assert rows["inst-1"]["divergent"] is False
    assert rows["inst-1"]["in_a"]["eval_resolved"] is True
    assert rows["inst-1"]["in_b"]["eval_resolved"] is True
    assert rows["inst-1"]["cost_delta"] == pytest.approx(0.04)

    assert rows["inst-2"]["divergent"] is True
    assert rows["inst-2"]["in_a"]["eval_resolved"] is True
    assert rows["inst-2"]["in_b"]["eval_resolved"] is False

    assert rows["inst-only-a"]["in_b"]["present"] is False
    assert rows["inst-only-a"]["divergent"] is True  # b.eval_resolved is None

    # Divergent rows must come before convergent ones in the sort.
    divergent_seen = True
    for row in body["instances"]:
        if not row["divergent"]:
            divergent_seen = False
        elif not divergent_seen:
            pytest.fail("Divergent rows must sort before convergent")


def test_runs_compare_404(client: TestClient) -> None:
    assert client.get("/runs/compare", params={"a": "ghost", "b": "run-b"}).status_code == 404


def test_runs_compare_self_400(client: TestClient) -> None:
    assert client.get("/runs/compare", params={"a": "run-a", "b": "run-a"}).status_code == 400


def test_analytics_404(client: TestClient) -> None:
    assert client.get("/runs/ghost/analytics").status_code == 404
