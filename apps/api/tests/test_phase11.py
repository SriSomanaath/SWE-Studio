from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _write_traj(path: Path, steps: int = 3) -> None:
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
                "instance_cost": 0.1,
                "tokens_sent": 100,
                "tokens_received": 50,
                "api_calls": 1,
            },
        },
    }
    path.write_text(json.dumps(payload))


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    run = tmp_path / "run-P11"
    run.mkdir()
    _write_traj(run / "alpha.traj", steps=4)
    _write_traj(run / "beta.traj", steps=2)

    monkeypatch.setenv("TRAJECTORIES_DIR", str(tmp_path))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "index.sqlite"))
    monkeypatch.setenv("INDEXER_ENABLED", "false")
    monkeypatch.setenv("APP_SECRET", "test-secret-do-not-leak")
    monkeypatch.setenv("SITE_URL", "https://swe.studio.test")

    import app.config as config_mod
    import app.db as db_mod
    import app.indexer as idx
    import app.main as main_mod
    import app.routers.ingest as ingest_mod
    import app.shares as shares_mod
    import app.trajectory_store as store
    from app.config import Settings

    config_mod.settings = Settings()
    for m in (store, idx, db_mod, ingest_mod, shares_mod):
        m.settings = config_mod.settings
    store.root_diagnostics.cache_clear()
    db_mod.reset()
    idx.bulk_reindex()
    return TestClient(main_mod.app)


# --- Shares CRUD ---


def test_share_create_resolves_publicly(client: TestClient) -> None:
    res = client.post(
        "/shares",
        json={"kind": "trajectory", "run_id": "run-P11", "trajectory_id": "alpha"},
        headers={"X-Author": "ada"},
    )
    assert res.status_code == 201
    body = res.json()
    token = body["token"]
    assert body["author"] == "ada"
    assert body["kind"] == "trajectory"
    assert body["url"].startswith("https://swe.studio.test/s/")

    # Resolve without auth
    res = client.get(f"/shares/{token}/resolve")
    assert res.status_code == 200
    resolved = res.json()
    assert resolved["target_run_id"] == "run-P11"
    assert resolved["target_traj_id"] == "alpha"


def test_share_for_run(client: TestClient) -> None:
    res = client.post("/shares", json={"kind": "run", "run_id": "run-P11"})
    assert res.status_code == 201
    token = res.json()["token"]
    resolved = client.get(f"/shares/{token}/resolve").json()
    assert resolved["kind"] == "run"
    assert resolved["target_run_id"] == "run-P11"


def test_share_for_showcase(client: TestClient) -> None:
    # First seed a showcase entry.
    client.post(
        "/showcase",
        json={
            "slug": "demo",
            "run_id": "run-P11",
            "trajectory_id": "alpha",
            "title": "demo",
        },
    )
    res = client.post("/shares", json={"kind": "showcase", "slug": "demo"})
    assert res.status_code == 201
    token = res.json()["token"]
    resolved = client.get(f"/shares/{token}/resolve").json()
    assert resolved["kind"] == "showcase"
    assert resolved["target_slug"] == "demo"


def test_share_validates_target_exists(client: TestClient) -> None:
    res = client.post(
        "/shares", json={"kind": "trajectory", "run_id": "run-P11", "trajectory_id": "ghost"}
    )
    assert res.status_code == 404


def test_share_revoke(client: TestClient) -> None:
    res = client.post("/shares", json={"kind": "run", "run_id": "run-P11"})
    token = res.json()["token"]
    assert client.delete(f"/shares/{token}").status_code == 204
    assert client.get(f"/shares/{token}/resolve").status_code == 410


def test_share_expiry(client: TestClient) -> None:
    res = client.post(
        "/shares",
        json={"kind": "run", "run_id": "run-P11", "ttl_seconds": 1},
    )
    token = res.json()["token"]
    assert client.get(f"/shares/{token}/resolve").status_code == 200
    # Mutate the row's expires_at directly to avoid sleeping in tests.
    import app.db as db_mod

    with db_mod.write_tx() as conn:
        conn.execute("UPDATE shares SET expires_at = ? WHERE token = ?", (time.time() - 60, token))
    assert client.get(f"/shares/{token}/resolve").status_code == 410


def test_share_invalid_kind(client: TestClient) -> None:
    res = client.post(
        "/shares",
        json={"kind": "garbage", "run_id": "run-P11"},
    )
    assert res.status_code == 422 or res.status_code == 400


def test_share_disabled_when_no_secret(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.config as config_mod
    import app.shares as shares_mod

    monkeypatch.setattr(shares_mod.settings, "app_secret", "")
    try:
        res = client.post("/shares", json={"kind": "run", "run_id": "run-P11"})
        assert res.status_code == 503
    finally:
        monkeypatch.setattr(shares_mod.settings, "app_secret", config_mod.settings.app_secret)


# --- Listing + auth bypass on resolve --


def test_share_listing(client: TestClient) -> None:
    client.post("/shares", json={"kind": "run", "run_id": "run-P11"})
    client.post(
        "/shares",
        json={"kind": "trajectory", "run_id": "run-P11", "trajectory_id": "beta"},
    )
    body = client.get("/shares").json()
    assert len(body) >= 2
    assert all("url" in s for s in body)


# --- Embeddings status (degraded when dep missing) --


def test_embeddings_status_reports_unavailable(client: TestClient) -> None:
    res = client.get("/embeddings/status")
    assert res.status_code == 200
    body = res.json()
    # The test venv doesn't pin sentence-transformers, so we expect either:
    #  - available=True if the optional dep happens to be installed
    #  - available=False with a reason string otherwise
    assert isinstance(body["available"], bool)
    assert body["model"]
    assert body["indexed_count"] == (0 if not body["available"] else body["indexed_count"])


# --- /similar fallback to FTS when no embeddings exist --


def test_similar_falls_back_to_fts(client: TestClient) -> None:
    # No embeddings indexed (no sentence-transformers in the venv); auto mode
    # should fall back to FTS and still return a list.
    res = client.get("/runs/run-P11/trajectories/alpha/similar", params={"mode": "auto"})
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_similar_mode_semantic_empty_without_embeddings(client: TestClient) -> None:
    res = client.get("/runs/run-P11/trajectories/alpha/similar", params={"mode": "semantic"})
    assert res.status_code == 200
    assert res.json() == []


def test_similar_mode_validation(client: TestClient) -> None:
    assert (
        client.get("/runs/run-P11/trajectories/alpha/similar", params={"mode": "bogus"}).status_code
        == 422
    )
