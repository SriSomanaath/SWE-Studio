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
    run = tmp_path / "run-S7"
    run.mkdir()
    _write_traj(run / "alpha.traj", steps=4)
    _write_traj(run / "beta.traj", steps=6)
    (run / "results.json").write_text(
        json.dumps(
            {
                "completed_ids": ["alpha", "beta"],
                "submitted_ids": ["alpha", "beta"],
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
    import app.routers.ingest as ingest_mod
    import app.trajectory_store as store
    from app.config import Settings

    config_mod.settings = Settings()
    for m in (store, idx, db_mod, ingest_mod):
        m.settings = config_mod.settings
    store.root_diagnostics.cache_clear()
    db_mod.reset()
    idx.bulk_reindex()
    return TestClient(main_mod.app)


def test_showcase_create_get_list(client: TestClient) -> None:
    res = client.post(
        "/showcase",
        json={
            "slug": "alpha-fix",
            "run_id": "run-S7",
            "trajectory_id": "alpha",
            "title": "Two-line BooleanField fix",
            "description": "Cleaner than expected.",
            "pinned_step": 2,
        },
        headers={"X-Author": "ada"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["slug"] == "alpha-fix"
    assert body["author"] == "ada"
    assert body["pinned_step"] == 2

    res = client.get("/showcase/alpha-fix")
    assert res.status_code == 200
    assert res.json()["title"] == "Two-line BooleanField fix"

    res = client.get("/showcase")
    assert len(res.json()) == 1


def test_showcase_slug_validation(client: TestClient) -> None:
    for bad in ["", "Has Space", "starts-", "-ends", "_underscore"]:
        res = client.post(
            "/showcase",
            json={
                "slug": bad,
                "run_id": "run-S7",
                "trajectory_id": "alpha",
                "title": "x",
            },
        )
        assert res.status_code == 400, bad


def test_showcase_slug_is_normalized_to_lowercase(client: TestClient) -> None:
    res = client.post(
        "/showcase",
        json={
            "slug": "UPPER-SLUG",
            "run_id": "run-S7",
            "trajectory_id": "alpha",
            "title": "x",
        },
    )
    assert res.status_code == 201
    assert res.json()["slug"] == "upper-slug"


def test_showcase_duplicate_slug(client: TestClient) -> None:
    payload = {
        "slug": "dup",
        "run_id": "run-S7",
        "trajectory_id": "alpha",
        "title": "first",
    }
    assert client.post("/showcase", json=payload).status_code == 201
    res = client.post("/showcase", json=payload)
    assert res.status_code == 409


def test_showcase_missing_trajectory(client: TestClient) -> None:
    res = client.post(
        "/showcase",
        json={
            "slug": "ghost-traj",
            "run_id": "run-S7",
            "trajectory_id": "nope",
            "title": "x",
        },
    )
    assert res.status_code == 404


def test_showcase_pinned_step_bounds(client: TestClient) -> None:
    res = client.post(
        "/showcase",
        json={
            "slug": "out-of-bounds",
            "run_id": "run-S7",
            "trajectory_id": "alpha",
            "title": "x",
            "pinned_step": 99,
        },
    )
    assert res.status_code == 400


def test_showcase_update(client: TestClient) -> None:
    client.post(
        "/showcase",
        json={
            "slug": "to-update",
            "run_id": "run-S7",
            "trajectory_id": "alpha",
            "title": "old",
        },
    )
    res = client.patch(
        "/showcase/to-update",
        json={"title": "new", "pinned_step": 1},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "new"
    assert body["pinned_step"] == 1


def test_showcase_delete(client: TestClient) -> None:
    client.post(
        "/showcase",
        json={"slug": "to-del", "run_id": "run-S7", "trajectory_id": "alpha", "title": "x"},
    )
    assert client.delete("/showcase/to-del").status_code == 204
    assert client.delete("/showcase/to-del").status_code == 404


def test_showcase_cascade_on_trajectory_delete(client: TestClient, tmp_path: Path) -> None:
    client.post(
        "/showcase",
        json={
            "slug": "cascade",
            "run_id": "run-S7",
            "trajectory_id": "beta",
            "title": "test",
        },
    )
    # Delete the trajectory file and force a reindex.
    (tmp_path / "run-S7" / "beta.traj").unlink()
    import app.indexer as idx

    idx.bulk_reindex()
    # Showcase entry should have been cascaded out.
    res = client.get("/showcase/cascade")
    assert res.status_code == 404
