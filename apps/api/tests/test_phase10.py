from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

# --- Local HTTP receiver -----------------------------------------------------


class _Recorder(BaseHTTPRequestHandler):
    received: list[dict[str, Any]] = []
    fail_count = 0  # set per-test
    fail_status = 500

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode()
        signature = self.headers.get("X-Studio-Signature", "")
        _Recorder.received.append({"body": body, "signature": signature})
        if _Recorder.fail_count > 0:
            _Recorder.fail_count -= 1
            self.send_response(_Recorder.fail_status)
            self.end_headers()
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *_args: Any) -> None:  # silence stdout
        return


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def receiver() -> tuple[str, HTTPServer]:
    _Recorder.received = []
    _Recorder.fail_count = 0
    port = _free_port()
    server = HTTPServer(("127.0.0.1", port), _Recorder)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}/hook", server
    server.shutdown()
    thread.join(timeout=2)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    run = tmp_path / "run-P10"
    run.mkdir()
    payload = {
        "history": [{"role": "user", "content": "fix it"}],
        "trajectory": [
            {"thought": "", "action": "ls", "response": "", "observation": "", "messages": []}
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
    (run / "alpha.traj").write_text(json.dumps(payload))

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


# --- CRUD ------------------------------------------------------------------


def test_webhook_crud(client: TestClient) -> None:
    res = client.post(
        "/webhooks",
        json={
            "url": "https://example.com/hook",
            "events": ["trajectory.resolved"],
            "description": "alert me on resolves",
        },
    )
    assert res.status_code == 201
    body = res.json()
    wid = body["id"]
    assert body["url"] == "https://example.com/hook"
    assert body["events"] == ["trajectory.resolved"]
    assert body["secret"].startswith("whsec_")
    assert body["active"] is True

    assert client.get("/webhooks").json()[0]["id"] == wid
    assert client.get(f"/webhooks/{wid}").json()["id"] == wid

    res = client.patch(f"/webhooks/{wid}", json={"active": False})
    assert res.json()["active"] is False

    assert client.delete(f"/webhooks/{wid}").status_code == 204
    assert client.get(f"/webhooks/{wid}").status_code == 404


def test_webhook_rejects_bad_url(client: TestClient) -> None:
    assert client.post("/webhooks", json={"url": "ftp://bad", "events": []}).status_code == 400
    assert client.post("/webhooks", json={"url": "not-a-url", "events": []}).status_code == 400


# --- Signing ---------------------------------------------------------------


def test_sign_produces_verifiable_hmac() -> None:
    from app.webhooks import sign

    secret = "whsec_test"
    payload = b'{"event":"x"}'
    sig = sign(secret, payload)
    assert sig.startswith("sha256=")
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert hmac.compare_digest(sig, expected)


# --- End-to-end delivery (real receiver) -----------------------------------


def _dispatch(client: TestClient, event: str, data: dict[str, Any]) -> None:
    """Run the dispatch coroutine on a fresh loop so it works inside TestClient."""
    from app.webhooks import dispatch_for_test

    asyncio.run(dispatch_for_test(event, data))


def test_delivery_signs_and_records(client: TestClient, receiver: tuple[str, HTTPServer]) -> None:
    url, _ = receiver
    res = client.post(
        "/webhooks",
        json={"url": url, "events": ["trajectory.resolved"], "description": "test"},
    )
    secret = res.json()["secret"]
    wid = res.json()["id"]

    _dispatch(client, "trajectory.resolved", {"run_id": "run-P10", "trajectory_id": "alpha"})

    assert len(_Recorder.received) == 1
    delivered = _Recorder.received[0]
    body = delivered["body"]
    envelope = json.loads(body)
    assert envelope["event"] == "trajectory.resolved"
    assert envelope["data"] == {"run_id": "run-P10", "trajectory_id": "alpha"}
    expected_sig = "sha256=" + hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    assert delivered["signature"] == expected_sig

    deliveries = client.get(f"/webhooks/{wid}/deliveries").json()
    assert len(deliveries) == 1
    assert deliveries[0]["success"] is True
    assert deliveries[0]["status_code"] == 200
    assert deliveries[0]["attempts"] == 1


def test_event_filter(client: TestClient, receiver: tuple[str, HTTPServer]) -> None:
    url, _ = receiver
    client.post("/webhooks", json={"url": url, "events": ["trajectory.resolved"]})

    _dispatch(client, "summary.generated", {"hello": "world"})
    assert _Recorder.received == []  # filtered out

    _dispatch(client, "trajectory.resolved", {"x": "y"})
    assert len(_Recorder.received) == 1


def test_no_events_means_all(client: TestClient, receiver: tuple[str, HTTPServer]) -> None:
    url, _ = receiver
    client.post("/webhooks", json={"url": url, "events": []})

    _dispatch(client, "summary.generated", {"a": 1})
    _dispatch(client, "bookmark.created", {"b": 2})
    assert len(_Recorder.received) == 2


def test_inactive_hook_skipped(client: TestClient, receiver: tuple[str, HTTPServer]) -> None:
    url, _ = receiver
    wid = client.post("/webhooks", json={"url": url, "events": []}).json()["id"]
    client.patch(f"/webhooks/{wid}", json={"active": False})

    _dispatch(client, "trajectory.resolved", {})
    assert _Recorder.received == []


def test_retries_on_failure_then_records(
    client: TestClient, receiver: tuple[str, HTTPServer]
) -> None:
    url, _ = receiver
    wid = client.post("/webhooks", json={"url": url, "events": []}).json()["id"]

    # First 4 attempts fail with 500; the worker gives up after 4.
    _Recorder.fail_count = 4

    # Speed the backoff up so the test finishes quickly.
    import app.webhooks as webhooks_mod

    backoff_before = webhooks_mod._BACKOFF_BASE
    webhooks_mod._BACKOFF_BASE = 0.0
    try:
        _dispatch(client, "trajectory.resolved", {"alpha": True})
    finally:
        webhooks_mod._BACKOFF_BASE = backoff_before

    deliveries = client.get(f"/webhooks/{wid}/deliveries").json()
    assert len(deliveries) == 1
    record = deliveries[0]
    assert record["success"] is False
    assert record["attempts"] == 4
    assert record["status_code"] == 500
    assert "HTTP 500" in (record["error"] or "")
