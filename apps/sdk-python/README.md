# swe-studio-sdk

Push coding-agent trajectories to a [SWE Studio](https://github.com/<your-org>/SWE-Studio) instance from any Python agent.

The SDK wraps the Studio `/ingest` endpoint with a context manager. Each step you record is pushed to Studio immediately, so its live mode lights up while your agent is still running.

## Install

```bash
pip install swe-studio-sdk
```

## Quick start

```python
from swe_studio_sdk import attach

with attach(
    run_id="my-aider-run",
    trajectory_id="issue-42",
    base_url="http://localhost:8080",
) as ctx:
    ctx.user_message("Fix the off-by-one in foo.py")

    for thought, action, observation in agent_loop():
        ctx.step(thought=thought, action=action, observation=observation)

    ctx.finish(
        exit_status="submitted",
        submission=final_patch,
        eval="resolved",
        instance_cost=0.27,
        tokens_sent=18420,
        tokens_received=1923,
    )
```

Open `http://localhost:3001/live` in another tab while this runs — Studio will pick up each step in real time.

## Integration recipes

### Aider

```python
from swe_studio_sdk import attach

with attach("aider-run", issue_id) as ctx:
    ctx.user_message(issue_body)
    for response in coder.run_stream(issue_body):
        ctx.step(
            thought=response.reasoning or "",
            action=response.edit_command or "",
            observation=response.test_output or "",
        )
    ctx.finish(
        exit_status="submitted" if coder.aider_done else "exit_forfeit",
        submission=coder.last_diff,
        eval="resolved" if coder.tests_passing else "failed",
        instance_cost=coder.usage.total_cost_usd,
        tokens_sent=coder.usage.prompt_tokens,
        tokens_received=coder.usage.completion_tokens,
        api_calls=coder.usage.requests,
    )
```

### OpenHands

```python
from swe_studio_sdk import attach
from openhands.events import Action, Observation

with attach("openhands-run", task_id) as ctx:
    ctx.user_message(task.description)
    async for ev in agent.stream():
        if isinstance(ev, Action):
            ctx.step(thought=ev.thought, action=ev.command)
        elif isinstance(ev, Observation):
            # Patch the most recent step with its observation.
            ctx.step(observation=ev.content)
    ctx.finish(exit_status=agent.exit_status, submission=agent.final_diff)
```

### Custom agent

```python
from swe_studio_sdk import attach

with attach("my-custom-run", instance_id, flush_every=3) as ctx:  # flush every 3 steps
    ctx.user_message(problem)
    for tool_call in run():
        ctx.step(thought=tool_call.thought, action=tool_call.shell, observation=tool_call.stdout)
    ctx.finish(exit_status="submitted", submission=diff)
```

## API

```python
attach(
    run_id: str,
    trajectory_id: str,
    *,
    base_url: str = "http://localhost:8080",
    author: str | None = None,
    system_prompt: str | None = None,
    flush_every: int = 1,
    client: StudioClient | None = None,
) -> TrajectoryContext
```

- `flush_every` — push to Studio every N steps (default 1, i.e. live).
- `author` — sent as `X-Author` on auxiliary endpoints (e.g. `annotate()`).

`TrajectoryContext` methods:
- `user_message(content)`
- `step(thought=, action=, observation=, response=)`
- `finish(exit_status=, submission=, eval=, instance_cost=, tokens_sent=, tokens_received=, api_calls=)` → returns the final ingest result.

`StudioClient` exposes `ingest()` and `annotate()` if you need low-level control.

## Versioning

Pre-1.0. The API may change in patch releases until 1.0.

## License

MIT.
