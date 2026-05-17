from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


PATCH_A = """diff --git a/foo.py b/foo.py
--- a/foo.py
+++ b/foo.py
@@ -1,2 +1,3 @@
 def foo():
-    return 1
+    # added
+    return 2
diff --git a/bar.py b/bar.py
--- a/bar.py
+++ b/bar.py
@@ -1,1 +1,1 @@
-x = 1
+x = 2
"""

PATCH_B = """diff --git a/foo.py b/foo.py
--- a/foo.py
+++ b/foo.py
@@ -1,2 +1,2 @@
 def foo():
-    return 1
+    return 9
diff --git a/baz.py b/baz.py
--- a/baz.py
+++ b/baz.py
@@ -1,1 +1,1 @@
-y = 1
+y = 2
"""


def _write_traj(path: Path, *, steps: int, submission: str | None, problem: str) -> None:
    payload = {
        "history": [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": problem},
        ],
        "trajectory": [
            {
                "thought": f"thought reading {path.stem}",
                "action": f"grep -rn 'BooleanField' django/",
                "response": "",
                "observation": "django/db/models/fields/__init__.py:1402",
                "messages": [],
            }
            for _ in range(steps)
        ],
        "info": {
            "exit_status": "submitted" if submission else "exit_forfeit",
            "submission": submission,
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
    run = tmp_path / "run-S"
    run.mkdir()
    _write_traj(
        run / "alpha.traj",
        steps=3,
        submission=PATCH_A,
        problem="BooleanField does not accept 0 in Django forms",
    )
    _write_traj(
        run / "beta.traj",
        steps=4,
        submission=PATCH_B,
        problem="Flask sessions raise TypeError when datetime is timezone-aware",
    )
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


# --- FTS5 search ---


def test_search_finds_problem(client: TestClient) -> None:
    res = client.get("/search", params={"q": "BooleanField"})
    assert res.status_code == 200
    body = res.json()
    assert body["query"] == "BooleanField"
    assert any(h["trajectory_id"] == "alpha" for h in body["hits"])
    assert all(h["kind"] == "trajectory" for h in body["hits"])


def test_search_finds_step_text(client: TestClient) -> None:
    res = client.get("/search", params={"q": "django models fields"})
    hits = res.json()["hits"]
    assert hits, "expected at least one step_text hit"
    assert any(h["field"] in ("step_text", "problem") for h in hits)


def test_search_scoped_to_run(client: TestClient) -> None:
    res = client.get("/search", params={"q": "Flask", "run_id": "run-S"})
    hits = res.json()["hits"]
    assert all(h["run_id"] == "run-S" for h in hits)


def test_search_kind_filter(client: TestClient) -> None:
    res = client.get("/search", params={"q": "BooleanField", "kind": "annotation"})
    assert res.json()["hits"] == []  # no annotations yet


def test_search_annotations(client: TestClient) -> None:
    client.post(
        "/runs/run-S/trajectories/alpha/annotations",
        json={"step_index": 1, "body": "watch out for the boolean coercion edge case"},
        headers={"X-Author": "ada"},
    )
    res = client.get("/search", params={"q": "coercion"})
    body = res.json()
    assert any(h["kind"] == "annotation" and h["step_index"] == 1 for h in body["hits"])


def test_search_handles_special_chars(client: TestClient) -> None:
    # Quotes and parens used to crash FTS5 with a "syntax error" — sanitizer
    # should strip them.
    res = client.get("/search", params={"q": "BooleanField(0)"})
    assert res.status_code == 200


def test_search_rejects_empty(client: TestClient) -> None:
    assert client.get("/search", params={"q": "   "}).json()["hits"] == []


# --- Diff intelligence ---


def test_compare_includes_diff_analysis(client: TestClient) -> None:
    res = client.get("/compare", params={"a": "run-S:alpha", "b": "run-S:beta"})
    assert res.status_code == 200
    da = res.json()["diff_analysis"]
    assert da is not None
    assert da["files_in_both"] == 1     # foo.py
    assert da["files_only_a"] == 1      # bar.py
    assert da["files_only_b"] == 1      # baz.py
    paths_in_both = [f["path"] for f in da["files"] if f["in_a"] and f["in_b"]]
    assert paths_in_both == ["foo.py"]


def test_compare_diff_line_counts(client: TestClient) -> None:
    res = client.get("/compare", params={"a": "run-S:alpha", "b": "run-S:beta"})
    files = {f["path"]: f for f in res.json()["diff_analysis"]["files"]}
    # PATCH_A adds 2 lines, removes 1 from foo.py
    assert files["foo.py"]["added_a"] == 2
    assert files["foo.py"]["removed_a"] == 1
    # PATCH_B adds 1, removes 1 from foo.py
    assert files["foo.py"]["added_b"] == 1
    assert files["foo.py"]["removed_b"] == 1
    # bar.py only in A
    assert files["bar.py"]["in_a"] and not files["bar.py"]["in_b"]


def test_diff_parser_unit() -> None:
    from app.diff import parse_unified_diff

    files = parse_unified_diff(PATCH_A)
    assert set(files) == {"foo.py", "bar.py"}
    assert files["foo.py"].added == 2
    assert files["foo.py"].removed == 1


def test_diff_parser_handles_none() -> None:
    from app.diff import parse_unified_diff

    assert parse_unified_diff(None) == {}
    assert parse_unified_diff("") == {}
