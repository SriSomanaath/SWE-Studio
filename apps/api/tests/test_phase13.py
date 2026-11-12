from __future__ import annotations

import json
import time
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
            {"thought": "", "action": "ls", "response": "", "observation": "", "messages": []}
            for _ in range(steps)
        ],
        "info": {
            "exit_status": "submitted",
            "submission": None,
            "model_stats": {
                "instance_cost": 0.1, "tokens_sent": 100, "tokens_received": 50, "api_calls": 1
            },
        },
    }
    path.write_text(json.dumps(payload))


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    run = tmp_path / "run-P13"
    run.mkdir()
    _write_traj(run / "alpha.traj", steps=3)

    monkeypatch.setenv("TRAJECTORIES_DIR", str(tmp_path))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "index.sqlite"))
    monkeypatch.setenv("INDEXER_ENABLED", "false")

    import app.config as config_mod
    import app.db as db_mod
    import app.indexer as idx
    import app.main as main_mod
    import app.routers.ingest as ingest_mod
    import app.routers.replay as replay_mod
    import app.trajectory_store as store
    from app.config import Settings

    config_mod.settings = Settings()
    for m in (store, idx, db_mod, ingest_mod, replay_mod):
        m.settings = config_mod.settings
    store.root_diagnostics.cache_clear()
    db_mod.reset()
    idx.bulk_reindex()
    return TestClient(main_mod.app)


# --- Workspaces -------------------------------------------------------------


def test_default_workspace_seeded(client: TestClient) -> None:
    res = client.get("/workspaces")
    assert res.status_code == 200
    ws = res.json()
    assert any(w["id"] == "default" for w in ws)


def test_me_without_auth(client: TestClient) -> None:
    res = client.get("/me")
    assert res.status_code == 200
    body = res.json()
    assert body["user"] is None
    assert body["active_workspace_id"] == "default"
    assert any(w["id"] == "default" for w in body["workspaces"])


def test_me_with_auth_creates_user(client: TestClient) -> None:
    res = client.get(
        "/me",
        headers={
            "X-Studio-User": "github:42",
            "X-Studio-Name": "Ada",
            "X-Studio-Email": "ada@example.com",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["user"]["id"] == "github:42"
    assert body["user"]["email"] == "ada@example.com"
    # Default workspace is auto-joined.
    assert any(w["id"] == "default" for w in body["workspaces"])


def test_create_workspace(client: TestClient) -> None:
    res = client.post(
        "/workspaces",
        json={"id": "acme", "name": "Acme research"},
        headers={"X-Studio-User": "github:42"},
    )
    assert res.status_code == 201
    assert res.json()["id"] == "acme"

    # Listing /me as that user should now include Acme.
    me = client.get("/me", headers={"X-Studio-User": "github:42"}).json()
    assert any(w["id"] == "acme" for w in me["workspaces"])


def test_create_workspace_validates_slug(client: TestClient) -> None:
    res = client.post(
        "/workspaces",
        json={"id": "Has Space", "name": "Bad"},
    )
    assert res.status_code == 400


def test_create_workspace_409(client: TestClient) -> None:
    client.post("/workspaces", json={"id": "duo", "name": "Duo"})
    res = client.post("/workspaces", json={"id": "duo", "name": "Duo"})
    assert res.status_code == 409


# --- Replay -----------------------------------------------------------------


def test_replay_creates_fresh_run(client: TestClient, tmp_path: Path) -> None:
    res = client.post(
        "/runs/run-P13/trajectories/alpha/replay",
        params={"delay": 0.1},
    )
    assert res.status_code == 202
    body = res.json()
    assert body["new_run_id"].startswith("replay-run-P13-")
    assert body["trajectory_id"] == "alpha"
    assert body["step_count"] == 3

    # Wait for the replay worker to finish writing.
    new_path = tmp_path / body["new_run_id"] / "alpha.traj"
    deadline = time.time() + 3.0
    while time.time() < deadline:
        if new_path.exists() and json.loads(new_path.read_text())["info"]["exit_status"] == "submitted":
            break
        time.sleep(0.1)
    assert new_path.exists()
    final = json.loads(new_path.read_text())
    assert len(final["trajectory"]) == 3


def test_replay_404_for_missing_traj(client: TestClient) -> None:
    assert (
        client.post("/runs/run-P13/trajectories/ghost/replay").status_code == 404
    )


# --- Presence ---------------------------------------------------------------


def test_presence_upsert_and_snapshot(client: TestClient) -> None:
    res = client.post(
        "/runs/run-P13/trajectories/alpha/presence",
        params={"step": 1, "user_id": "ada"},
        headers={"X-Studio-Name": "Ada"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["run_id"] == "run-P13"
    assert any(v["user_id"] == "ada" and v["step_index"] == 1 for v in body["viewers"])

    snap = client.get("/runs/run-P13/trajectories/alpha/presence").json()
    assert any(v["user_id"] == "ada" for v in snap["viewers"])


def test_presence_remove(client: TestClient) -> None:
    client.post(
        "/runs/run-P13/trajectories/alpha/presence",
        params={"step": 2, "user_id": "ben"},
    )
    client.delete(
        "/runs/run-P13/trajectories/alpha/presence",
        params={"user_id": "ben"},
    )
    snap = client.get("/runs/run-P13/trajectories/alpha/presence").json()
    assert not any(v["user_id"] == "ben" for v in snap["viewers"])


def test_presence_multiple_viewers(client: TestClient) -> None:
    client.post(
        "/runs/run-P13/trajectories/alpha/presence",
        params={"step": 0, "user_id": "ada"},
    )
    client.post(
        "/runs/run-P13/trajectories/alpha/presence",
        params={"step": 2, "user_id": "ben"},
    )
    snap = client.get("/runs/run-P13/trajectories/alpha/presence").json()
    ids = {v["user_id"] for v in snap["viewers"]}
    assert {"ada", "ben"}.issubset(ids)
