"""Real litellm request/response paths against local fake provider servers."""

import json
import threading
from collections.abc import Callable
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

pytest.importorskip("litellm")
from app.agent.llm import chat  # noqa: E402


@contextmanager
def fake_provider(respond: Callable[[dict], dict]):
    """Serve `respond(request_body)` as JSON; yields (base_url, seen)."""
    seen: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            seen["path"] = self.path
            seen["auth"] = self.headers.get("Authorization", "")
            seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            out = json.dumps(respond(seen["body"])).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", seen
    finally:
        server.shutdown()


def test_hosted_vllm_hits_vllm_base_url_without_leaking_keys(monkeypatch) -> None:
    openai_reply = lambda body: {  # noqa: E731
        "id": "x", "object": "chat.completion", "created": 0, "model": body["model"],
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": "THOUGHT: t\nACTION: submit"}}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
    }
    with fake_provider(openai_reply) as (base, seen):
        monkeypatch.setenv("VLLM_BASE_URL", f"{base}/v1")
        result = chat(
            messages=[{"role": "user", "content": "hi"}],
            model="hosted_vllm/Qwen/Qwen2.5-Coder-7B-Instruct",
            api_key="sk-ant-must-not-leak",
        )
    assert seen["path"] == "/v1/chat/completions"
    assert seen["body"]["model"] == "Qwen/Qwen2.5-Coder-7B-Instruct"
    assert "sk-ant-must-not-leak" not in seen["auth"]
    assert "cache_control" not in json.dumps(seen["body"])  # Claude-only feature
    assert result.text.endswith("ACTION: submit") and result.prompt_tokens == 7


def test_claude_requests_set_cache_breakpoints_and_cached_tokens_cut_cost(monkeypatch) -> None:
    def anthropic_reply(cache_read: int, fresh: int) -> Callable[[dict], dict]:
        return lambda body: {
            "id": "msg_1", "type": "message", "role": "assistant", "model": body["model"],
            "content": [{"type": "text", "text": "THOUGHT: t\nACTION: submit"}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": fresh, "output_tokens": 10,
                      "cache_read_input_tokens": cache_read, "cache_creation_input_tokens": 0},
        }

    history = [
        {"role": "system", "content": "You are an agent. " * 300},
        {"role": "user", "content": "fix the bug"},
        {"role": "assistant", "content": "THOUGHT: look\nACTION: bash ls"},
        {"role": "user", "content": "OBSERVATION:\nREADME"},
    ]
    results, bodies = [], []
    for cache_read, fresh in ((0, 2000), (1900, 100)):  # same 2000 prompt tokens, cold vs warm
        with fake_provider(anthropic_reply(cache_read, fresh)) as (base, seen):
            monkeypatch.setenv("ANTHROPIC_API_BASE", base)
            results.append(chat(messages=history, model="claude-sonnet-4-5", api_key="sk-test"))
            bodies.append(seen["body"])

    body = bodies[0]
    # Breakpoint 1: the system prompt. Breakpoint 2: the latest turn, so the
    # next step reads everything before it from cache.
    assert any("cache_control" in block for block in body["system"])
    assert "cache_control" in json.dumps(body["messages"][-1])
    cold, warm = results
    assert warm.cached_tokens == 1900 and cold.cached_tokens == 0
    assert 0 < warm.cost_usd < cold.cost_usd * 0.3  # cache reads bill at ~10%


def test_agent_loop_runs_native_tool_calls_and_answers_each_by_id(tmp_path) -> None:
    import subprocess

    from app.agent import AgentConfig, run_agent
    from app.agent.llm import LLMResult

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], cwd=repo, check=True)

    turns = iter([
        LLMResult(text="Fix the constant.", reasoning="x should be 2", tool_calls=[
            {"id": "call_1", "name": "write", "arguments": json.dumps({"path": "a.py", "content": "x = 2\n"})}]),
        LLMResult(text="", tool_calls=[{"id": "call_2", "name": "submit", "arguments": "{}"}]),
    ])
    seen_history: list = []

    def fake_chat(*, messages, tools=None, **_):
        assert {t["function"]["name"] for t in tools} == {"bash", "read", "write", "submit", "finish"}
        seen_history[:] = messages
        return next(turns)

    result = run_agent(AgentConfig(workdir=repo, problem_statement="set x to 2"), run_id="r",
                       trajectory_id="t", trajectories_dir=tmp_path / "out", chat_fn=fake_chat)

    assert result.exit_status == "submitted" and (repo / "a.py").read_text() == "x = 2\n"
    assistant, tool_reply = seen_history[-2], seen_history[-1]  # history sent on the 2nd call
    assert assistant["tool_calls"][0]["id"] == "call_1" and assistant["reasoning_content"] == "x should be 2"
    assert tool_reply == {"role": "tool", "tool_call_id": "call_1", "content": "wrote 6 bytes to a.py"}
    traj = json.loads(result.file_path.read_text())
    from app.schemas import TrajectoryFile

    TrajectoryFile.model_validate(traj)  # what /ingest does: tool-call turns have content=None
    assert "+x = 2" in traj["info"]["submission"]
    assert traj["trajectory"][0]["action"] == "write a.py\nx = 2"


def test_rate_limits_back_off_instead_of_killing_the_run(monkeypatch) -> None:
    import litellm

    from app.agent import llm

    calls, sleeps = [], []
    ok = litellm.ModelResponse(choices=[{"message": {"role": "assistant", "content": "hi"}}],
                               usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})

    def fake_completion(**_):
        calls.append(1)
        if len(calls) < 3:
            raise litellm.RateLimitError("3 RPM", llm_provider="moonshot", model="kimi-k3")
        return ok

    monkeypatch.setattr(litellm, "completion", fake_completion)
    monkeypatch.setattr(llm.time, "sleep", sleeps.append)
    assert llm.chat(messages=[{"role": "user", "content": "x"}], model="moonshot/kimi-k3").text == "hi"
    assert len(calls) == 3 and sleeps == [10, 20]  # waits long enough for a per-minute window
