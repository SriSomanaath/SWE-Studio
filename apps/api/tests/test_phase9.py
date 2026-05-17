from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _write_traj(path: Path, *, steps: list[tuple[str, str]], exit_status: str = "submitted",
                cost: float = 0.1) -> None:
    payload = {
        "history": [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": f"Fix {path.stem}: refactor and submit"},
        ],
        "trajectory": [
            {
                "thought": f"step {i}",
                "action": action,
                "response": "",
                "observation": obs,
                "messages": [],
            }
            for i, (action, obs) in enumerate(steps)
        ],
        "info": {
            "exit_status": exit_status,
            "submission": "diff --git a/x b/x\n" if exit_status == "submitted" else None,
            "model_stats": {
                "instance_cost": cost,
                "tokens_sent": 1000 * len(steps),
                "tokens_received": 250 * len(steps),
                "api_calls": len(steps),
            },
        },
    }
    path.write_text(json.dumps(payload))


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    run = tmp_path / "run-P9"
    run.mkdir()
    # Two "ls / grep / sed" trajectories — should cluster.
    _write_traj(run / "alpha.traj", steps=[("ls -la", "files"), ("grep BooleanField django/", "found"), ("sed -i s/x/y/ x", "")])
    _write_traj(run / "beta.traj", steps=[("ls", "files"), ("grep django models", "found"), ("sed -i s/a/b/ y", "")])
    # One "python / pytest" trajectory — different cluster.
    _write_traj(run / "gamma.traj", steps=[("python repro.py", "fail"), ("pytest tests/", "pass")], exit_status="exit_forfeit", cost=0.4)

    (run / "results.json").write_text(
        json.dumps(
            {
                "completed_ids": ["alpha", "beta", "gamma"],
                "submitted_ids": ["alpha", "beta"],
                "resolved_ids": ["alpha"],
            }
        )
    )

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

    config_mod.settings = Settings()
    for m in (store, idx, db_mod, ingest_mod):
        m.settings = config_mod.settings
    store.root_diagnostics.cache_clear()
    db_mod.reset()
    idx.bulk_reindex()
    return TestClient(main_mod.app)


# --- Dataset export ---


def test_export_jsonl_streams_records(client: TestClient) -> None:
    res = client.get("/runs/run-P9/export.jsonl")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/x-ndjson")
    records = [json.loads(line) for line in res.text.splitlines() if line.strip()]
    assert len(records) == 3
    ids = {r["instance_id"] for r in records}
    assert ids == {"alpha", "beta", "gamma"}
    alpha = next(r for r in records if r["instance_id"] == "alpha")
    assert alpha["resolved"] is True
    assert alpha["submitted"] is True
    assert len(alpha["steps"]) == 3
    assert alpha["steps"][0]["action"].startswith("ls")


def test_export_manifest(client: TestClient) -> None:
    res = client.get("/runs/run-P9/manifest.json")
    body = res.json()
    assert body["record_count"] == 3
    assert body["stats"]["resolved_count"] == 1
    assert body["stats"]["submitted_count"] == 2
    assert body["stats"]["pass_rate"] == pytest.approx(1 / 3)
    assert body["format"] == "jsonl"
    assert "studio_version" in body
    assert "instance_id" in {f for f in body["schema_fields"]}


def test_export_404(client: TestClient) -> None:
    assert client.get("/runs/ghost/export.jsonl").status_code == 404


# --- Insights ---


def test_insights_clusters_by_fingerprint(client: TestClient) -> None:
    res = client.get("/runs/run-P9/insights")
    assert res.status_code == 200
    body = res.json()
    assert body["trajectory_count"] == 3
    # alpha + beta share "ls·grep·sed" (in some order); gamma is solo.
    sizes = sorted(c["size"] for c in body["clusters"])
    assert sizes == [1, 2]
    big = next(c for c in body["clusters"] if c["size"] == 2)
    assert set(big["fingerprint"].split("·")) == {"ls", "grep", "sed"}
    assert set(big["sample_ids"]) == {"alpha", "beta"}


def test_insights_aggregates(client: TestClient) -> None:
    body = client.get("/runs/run-P9/insights").json()
    big = next(c for c in body["clusters"] if c["size"] == 2)
    assert big["resolved_count"] == 1     # alpha resolved
    assert big["submitted_count"] == 1    # beta submitted but not resolved
    assert big["failed_count"] == 1       # beta completed but not resolved


# --- Similarity ---


def test_similar_excludes_self_and_returns_peer(client: TestClient) -> None:
    res = client.get("/runs/run-P9/trajectories/alpha/similar", params={"limit": 5})
    assert res.status_code == 200
    hits = res.json()
    # alpha shares verbs with beta; gamma's verbs (python/pytest) are different.
    assert all(h["trajectory_id"] != "alpha" for h in hits)
    ids = [h["trajectory_id"] for h in hits]
    assert "beta" in ids
    # beta should outrank gamma (shared verb set).
    if "gamma" in ids:
        assert ids.index("beta") < ids.index("gamma")


def test_similar_404(client: TestClient) -> None:
    assert (
        client.get("/runs/run-P9/trajectories/ghost/similar").status_code == 404
    )


# --- HF dataset-card CLI ---


def test_dataset_card_writes_outputs(client: TestClient, tmp_path: Path) -> None:
    out = tmp_path / "hf-card"
    from app.tools.dataset_card import main as card_main

    rc = card_main(["--run", "run-P9", "--output", str(out)])
    assert rc == 0

    jsonl = (out / "data" / "run.jsonl").read_text().splitlines()
    assert len(jsonl) == 3

    info = json.loads((out / "dataset_info.json").read_text())
    assert info["splits"]["train"]["num_examples"] == 3
    assert "instance_id" in info["features"]
    assert info["features"]["steps"]["_type"] == "Sequence"

    readme = (out / "README.md").read_text()
    assert readme.startswith("---\n")
    assert "configs:" in readme
    assert "run-P9" in readme
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["record_count"] == 3
