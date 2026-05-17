from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _write_traj(path: Path, *, steps: int = 3) -> None:
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
                "observation": f"o{i}",
                "messages": [],
            }
            for i in range(steps)
        ],
        "info": {
            "exit_status": "submitted",
            "submission": "diff --git a/x b/x\n",
            "model_stats": {
                "instance_cost": 0.1,
                "tokens_sent": 1000,
                "tokens_received": 250,
                "api_calls": steps,
            },
        },
    }
    path.write_text(json.dumps(payload))


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    run_dir = tmp_path / "run-N"
    run_dir.mkdir()
    _write_traj(run_dir / "alpha.traj", steps=3)
    (run_dir / "results.json").write_text(
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

    from app.config import Settings
    import app.config as config_mod
    import app.trajectory_store as store
    import app.indexer as idx
    import app.db as db_mod
    import app.main as main_mod
    import app.routers.ingest as ingest_mod

    config_mod.settings = Settings()
    store.settings = config_mod.settings
    idx.settings = config_mod.settings
    db_mod.settings = config_mod.settings
    ingest_mod.settings = config_mod.settings

    store.root_diagnostics.cache_clear()
    db_mod.reset()
    idx.bulk_reindex()

    return TestClient(main_mod.app)


# --- annotations ---


def test_create_list_delete_annotation(client: TestClient) -> None:
    res = client.post(
        "/runs/run-N/trajectories/alpha/annotations",
        json={"step_index": 1, "body": "this looks weird"},
        headers={"X-Author": "ada"},
    )
    assert res.status_code == 201
    a = res.json()
    assert a["author"] == "ada"
    assert a["step_index"] == 1
    annotation_id = a["id"]

    res = client.get("/runs/run-N/trajectories/alpha/annotations")
    assert len(res.json()) == 1

    res = client.patch(
        f"/annotations/{annotation_id}",
        json={"body": "edited"},
        headers={"X-Author": "ada"},
    )
    assert res.status_code == 200
    assert res.json()["body"] == "edited"

    res = client.delete(f"/annotations/{annotation_id}")
    assert res.status_code == 204

    assert client.get("/runs/run-N/trajectories/alpha/annotations").json() == []


def test_annotation_anonymous_author(client: TestClient) -> None:
    res = client.post(
        "/runs/run-N/trajectories/alpha/annotations",
        json={"step_index": 0, "body": "hi"},
    )
    assert res.status_code == 201
    assert res.json()["author"] == "anonymous"


def test_annotation_empty_body(client: TestClient) -> None:
    res = client.post(
        "/runs/run-N/trajectories/alpha/annotations",
        json={"step_index": 0, "body": "   "},
        headers={"X-Author": "ada"},
    )
    assert res.status_code == 400


def test_annotation_on_missing_trajectory(client: TestClient) -> None:
    res = client.post(
        "/runs/run-N/trajectories/ghost/annotations",
        json={"step_index": 0, "body": "x"},
    )
    assert res.status_code == 404


# --- bookmarks ---


def test_bookmark_lifecycle(client: TestClient) -> None:
    res = client.put(
        "/bookmarks/run-N/alpha",
        json={"note": "interesting fix"},
        headers={"X-Author": "ada"},
    )
    assert res.status_code == 200
    assert res.json()["note"] == "interesting fix"

    res = client.get("/bookmarks?author=ada")
    assert len(res.json()) == 1

    # Upsert behavior: PUT again with new note overwrites.
    res = client.put(
        "/bookmarks/run-N/alpha",
        json={"note": "updated"},
        headers={"X-Author": "ada"},
    )
    assert res.json()["note"] == "updated"
    assert len(client.get("/bookmarks?author=ada").json()) == 1

    res = client.delete("/bookmarks/run-N/alpha", headers={"X-Author": "ada"})
    assert res.status_code == 204
    assert client.get("/bookmarks?author=ada").json() == []


def test_bookmark_different_authors_coexist(client: TestClient) -> None:
    client.put("/bookmarks/run-N/alpha", json={}, headers={"X-Author": "ada"})
    client.put("/bookmarks/run-N/alpha", json={}, headers={"X-Author": "ben"})
    assert len(client.get("/bookmarks").json()) == 2


# --- markdown export ---


def test_export_markdown(client: TestClient) -> None:
    client.post(
        "/runs/run-N/trajectories/alpha/annotations",
        json={"step_index": 1, "body": "note on step 2"},
        headers={"X-Author": "ada"},
    )
    res = client.get("/runs/run-N/trajectories/alpha/export.md")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/markdown")
    md = res.text
    assert "# run-N · alpha" in md
    assert "## Step 2" in md
    assert "_Note from ada:_ note on step 2" in md
    assert "## Final patch" in md


# --- ingest ---


def test_ingest_creates_traj_and_indexes(client: TestClient, tmp_path: Path) -> None:
    payload = {
        "history": [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "fix ingested"},
        ],
        "trajectory": [
            {"thought": "t", "action": "ls", "response": "", "observation": "", "messages": []}
        ],
        "info": {
            "exit_status": "submitted",
            "submission": "diff",
            "model_stats": {
                "instance_cost": 0.05,
                "tokens_sent": 500,
                "tokens_received": 100,
                "api_calls": 1,
            },
        },
    }
    res = client.post(
        "/ingest/runs/ingested-run/trajectories/inst-1?eval=resolved",
        json=payload,
    )
    assert res.status_code == 201
    body = res.json()
    assert body["run_id"] == "ingested-run"

    # File should now exist on disk in the trajectories dir.
    written = Path(body["file_path"])
    assert written.exists()
    assert written.parent.name == "ingested-run"

    # Should be reflected in the index immediately (the endpoint calls _reindex_run).
    res = client.get("/runs")
    ids = {r["id"] for r in res.json()}
    assert "ingested-run" in ids

    res = client.get("/runs/ingested-run/trajectories")
    assert len(res.json()) == 1
    assert res.json()[0]["eval"]["resolved"] is True


def test_ingest_rejects_unsafe_id(client: TestClient) -> None:
    res = client.post(
        "/ingest/runs/..%2Fescape/trajectories/inst",
        json={"history": [], "trajectory": [], "info": {}},
    )
    # FastAPI percent-decodes path params before our regex sees them.
    assert res.status_code in (400, 404)
