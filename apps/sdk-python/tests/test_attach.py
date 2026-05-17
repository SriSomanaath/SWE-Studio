"""SDK tests that boot a real uvicorn server in a background thread."""

from __future__ import annotations

import socket
import sys
import threading
import time
from pathlib import Path
from typing import Iterator

import httpx
import pytest

_API_PATH = Path(__file__).resolve().parents[2] / "api"
if str(_API_PATH) not in sys.path:
    sys.path.insert(0, str(_API_PATH))

from swe_studio_sdk import StudioClient, attach  # noqa: E402


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    monkeypatch.setenv("TRAJECTORIES_DIR", str(tmp_path))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "index.sqlite"))
    monkeypatch.setenv("INDEXER_ENABLED", "false")

    # Force a clean import of the API modules under the test env.
    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("app."):
            del sys.modules[mod]

    import uvicorn  # noqa: WPS433
    from app.config import Settings  # noqa: WPS433
    import app.config as config_mod
    import app.db as db_mod
    import app.indexer as idx
    import app.trajectory_store as store
    import app.routers.ingest as ingest_mod
    import app.main as main_mod

    config_mod.settings = Settings()
    for m in (db_mod, idx, store, ingest_mod):
        m.settings = config_mod.settings
    store.root_diagnostics.cache_clear()
    db_mod.reset()

    port = _free_port()
    config = uvicorn.Config(
        main_mod.app, host="127.0.0.1", port=port, log_level="warning", lifespan="off"
    )
    uv = uvicorn.Server(config)
    thread = threading.Thread(target=uv.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    # Wait for readiness.
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            httpx.get(f"{base_url}/health", timeout=0.2)
            break
        except httpx.HTTPError:
            time.sleep(0.05)
    else:
        uv.should_exit = True
        thread.join(timeout=2)
        pytest.fail("uvicorn server failed to come up")

    yield base_url

    uv.should_exit = True
    thread.join(timeout=3)


def test_attach_writes_growing_trajectory(server: str) -> None:
    with attach(
        "sdk-run",
        "issue-001",
        base_url=server,
        system_prompt="You are an agent.",
    ) as ctx:
        ctx.user_message("Fix the bug in foo.py")
        ctx.step(thought="read", action="ls", observation="foo.py")
        ctx.step(thought="patch", action="sed -i 's/x/y/' foo.py", observation="")
        ctx.finish(
            exit_status="submitted",
            submission="diff --git a/foo.py b/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-x\n+y\n",
            eval="resolved",
            instance_cost=0.07,
            tokens_sent=1200,
            tokens_received=180,
        )

    res = httpx.get(f"{server}/runs/sdk-run/trajectories/issue-001")
    body = res.json()
    assert len(body["steps"]) == 2
    assert body["eval"]["resolved"] is True
    assert body["info"]["model_stats"]["instance_cost"] == 0.07


def test_attach_flush_every(server: str) -> None:
    with attach("sdk-run", "issue-002", base_url=server, flush_every=5) as ctx:
        ctx.user_message("Do work")
        for i in range(3):
            ctx.step(thought=f"t{i}", action=f"echo {i}", observation="")
        snap = httpx.get(f"{server}/runs/sdk-run/trajectories/issue-002").json()
        # Only the user_message + initial flush created the trajectory; the
        # 3 steps haven't been flushed yet (threshold is 5).
        assert snap["info"]["exit_status"] == "running"
        ctx.finish(exit_status="exit_forfeit")
    final = httpx.get(f"{server}/runs/sdk-run/trajectories/issue-002").json()
    assert len(final["steps"]) == 3
    assert final["info"]["exit_status"] == "exit_forfeit"


def test_client_close_idempotent(server: str) -> None:
    client = StudioClient(base_url=server)
    client.close()
    client.close()
