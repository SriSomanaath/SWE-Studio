from fastapi.testclient import TestClient

from app import observability
from app.routers import ingest


def test_run_metrics_count_once_and_carry_cost_tokens_duration(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(ingest.settings, "trajectories_dir", tmp_path)
    monkeypatch.setattr(ingest.settings, "trajectories_bucket", "")
    monkeypatch.setattr(ingest.settings, "api_keys", [])
    monkeypatch.setattr(ingest.indexer, "_reindex_run", lambda _: None)
    from app.main import app

    client = TestClient(app)
    model = "metrics-test/model"  # unique label: the registry is process-global
    observability.run_started("mrun", "mtraj", model, "k8s")
    traj = {
        "history": [], "trajectory": [],
        "info": {"model": model, "exit_status": "submitted", "model_stats": {
            "instance_cost": 0.25, "tokens_sent": 1000, "tokens_received": 50, "tokens_cached": 800}},
    }
    url = "/ingest/runs/mrun/trajectories/mtraj"
    assert client.post(url, json=traj).status_code == 201
    assert client.post(url + "?eval=resolved", json=traj).status_code == 201  # verdict via re-post
    assert client.post(url + "/eval?result=failed").status_code == 204  # verdict-only endpoint
    assert client.post("/ingest/runs/mrun/trajectories/nope/eval?result=failed").status_code == 404

    m = client.get("/metrics").text
    label = f'model="{model}"'
    assert f'agent_runs_started_total{{executor="k8s",{label}}} 1.0' in m
    assert f'agent_runs_finished_total{{exit_status="submitted",{label}}} 1.0' in m  # not 2
    assert f'agent_evals_total{{{label},result="resolved"}} 1.0' in m
    assert f'agent_evals_total{{{label},result="failed"}} 1.0' in m
    assert f"agent_cost_usd_total{{{label}}} 0.25" in m
    assert f'llm_tokens_total{{kind="cached",{label}}} 800.0' in m
    assert f"agent_run_duration_seconds_count{{{label}}} 1" in m
