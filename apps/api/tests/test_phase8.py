from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _write_traj(path: Path, *, steps: int = 4) -> None:
    payload = {
        "history": [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": f"Fix {path.stem}"},
        ],
        "trajectory": [
            {
                "thought": f"think about step {i}",
                "action": f"grep -n 'foo' src/{path.stem}.py" if i % 2 == 0 else "sed -i 's/x/y/' x.py",
                "response": "",
                "observation": f"obs {i}",
                "messages": [],
            }
            for i in range(steps)
        ],
        "info": {
            "exit_status": "submitted",
            "submission": "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-x\n+y\n",
            "model_stats": {
                "instance_cost": 0.1,
                "tokens_sent": 1000,
                "tokens_received": 250,
                "api_calls": steps,
            },
        },
    }
    path.write_text(json.dumps(payload))


def _bootstrap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, api_keys: str = "") -> TestClient:
    run = tmp_path / "run-P8"
    run.mkdir()
    _write_traj(run / "alpha.traj", steps=4)
    (run / "results.json").write_text(
        json.dumps(
            {
                "completed_ids": ["alpha"],
                "submitted_ids": ["alpha"],
                "resolved_ids": ["alpha"],
            }
        )
    )

    monkeypatch.setenv("TRAJECTORIES_DIR", str(tmp_path))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "index.sqlite"))
    monkeypatch.setenv("INDEXER_ENABLED", "false")
    monkeypatch.setenv("API_KEYS", api_keys)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    from app.config import Settings
    import app.config as config_mod
    import app.trajectory_store as store
    import app.indexer as idx
    import app.db as db_mod
    import app.main as main_mod
    import app.routers.ingest as ingest_mod
    import app.auth as auth_mod

    config_mod.settings = Settings()
    for m in (store, idx, db_mod, ingest_mod, auth_mod):
        m.settings = config_mod.settings
    store.root_diagnostics.cache_clear()
    db_mod.reset()
    idx.bulk_reindex()
    return TestClient(main_mod.app)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    return _bootstrap(tmp_path, monkeypatch)


@pytest.fixture
def authed_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    return _bootstrap(tmp_path, monkeypatch, api_keys="secret-1,secret-2")


# --- /metrics ---


def test_metrics_endpoint(client: TestClient) -> None:
    # Make a couple of requests so counters tick.
    client.get("/runs")
    client.get("/health")

    res = client.get("/metrics")
    assert res.status_code == 200
    body = res.text
    assert "# TYPE api_requests_total counter" in body
    assert "# TYPE trajectories_indexed gauge" in body
    assert "api_request_duration_seconds_bucket" in body
    # The /runs call should have produced at least one labeled sample.
    assert 'route="/runs"' in body


def test_metrics_gauges_reflect_index(client: TestClient) -> None:
    res = client.get("/metrics").text
    assert "trajectories_indexed 1" in res
    assert "runs_indexed 1" in res


# --- API key auth ---


def test_writes_open_when_no_api_keys(client: TestClient) -> None:
    res = client.post(
        "/runs/run-P8/trajectories/alpha/annotations",
        json={"step_index": 0, "body": "open mode"},
    )
    assert res.status_code == 201


def test_writes_require_key_when_configured(authed_client: TestClient) -> None:
    res = authed_client.post(
        "/runs/run-P8/trajectories/alpha/annotations",
        json={"step_index": 0, "body": "no key"},
    )
    assert res.status_code == 401

    res = authed_client.post(
        "/runs/run-P8/trajectories/alpha/annotations",
        json={"step_index": 0, "body": "wrong key"},
        headers={"X-API-Key": "nope"},
    )
    assert res.status_code == 401

    res = authed_client.post(
        "/runs/run-P8/trajectories/alpha/annotations",
        json={"step_index": 0, "body": "right key"},
        headers={"X-API-Key": "secret-1"},
    )
    assert res.status_code == 201


def test_reads_stay_public_when_keys_configured(authed_client: TestClient) -> None:
    assert authed_client.get("/runs").status_code == 200
    assert authed_client.get("/runs/run-P8/trajectories/alpha").status_code == 200


def test_health_and_metrics_bypass_auth(authed_client: TestClient) -> None:
    assert authed_client.get("/health").status_code == 200
    assert authed_client.get("/metrics").status_code == 200


# --- Heuristic summary ---


def test_heuristic_summary_shape(client: TestClient) -> None:
    res = client.post(
        "/runs/run-P8/trajectories/alpha/summarize",
        params={"provider": "heuristic"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["provider"] == "heuristic"
    assert body["cached"] is False
    assert "Top action verbs" in body["body"]
    assert "`x.py`" in body["body"]


def test_summary_persists_as_annotation(client: TestClient) -> None:
    client.post("/runs/run-P8/trajectories/alpha/summarize", params={"provider": "heuristic"})
    res = client.get("/runs/run-P8/trajectories/alpha/annotations")
    notes = res.json()
    assert any(n["author"] == "@studio-ai" for n in notes)


def test_summary_cache_short_circuits(client: TestClient) -> None:
    a = client.post("/runs/run-P8/trajectories/alpha/summarize", params={"provider": "heuristic"}).json()
    b = client.post("/runs/run-P8/trajectories/alpha/summarize", params={"provider": "heuristic"}).json()
    assert b["cached"] is True
    assert a["created_at"] == b["created_at"]


def test_summary_force_regenerates(client: TestClient) -> None:
    client.post("/runs/run-P8/trajectories/alpha/summarize", params={"provider": "heuristic"})
    b = client.post(
        "/runs/run-P8/trajectories/alpha/summarize",
        params={"provider": "heuristic", "force": "true"},
    ).json()
    assert b["cached"] is False


def test_ai_summary_503_without_key(client: TestClient) -> None:
    res = client.post(
        "/runs/run-P8/trajectories/alpha/summarize",
        params={"provider": "ai"},
    )
    assert res.status_code == 503


def test_summary_status(client: TestClient) -> None:
    res = client.get("/summary/status")
    assert res.status_code == 200
    body = res.json()
    assert body["heuristic_available"] is True
    assert body["ai_available"] is False


# --- Structured logging --


def test_json_log_format(capsys: pytest.CaptureFixture[str]) -> None:
    import logging

    from app.observability import configure_logging

    configure_logging("INFO")
    logging.getLogger("test").info("hello", extra={"foo": "bar"})
    captured = capsys.readouterr()
    line = captured.out.strip().splitlines()[-1]
    parsed = json.loads(line)
    assert parsed["msg"] == "hello"
    assert parsed["foo"] == "bar"
    assert parsed["level"] == "INFO"
