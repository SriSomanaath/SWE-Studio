"""High-level `attach()` context manager for instrumenting an agent run."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Literal, Optional

from .client import StudioClient

EvalState = Literal["resolved", "submitted", "failed", "completed"]


class TrajectoryContext:
    """Buffers a trajectory and pushes incremental updates after each step.

    A new file is created on the first :meth:`step` or :meth:`user_message` so
    SWE Studio's live mode lights up immediately. Each subsequent step
    re-uploads the full payload — the indexer's atomic write + reindex makes
    this O(steps) which is cheap until you exceed ~100 steps. For very large
    trajectories, pass ``flush_every`` to throttle.
    """

    def __init__(
        self,
        client: StudioClient,
        run_id: str,
        trajectory_id: str,
        *,
        system_prompt: str | None = None,
        flush_every: int = 1,
    ) -> None:
        self._client = client
        self.run_id = run_id
        self.trajectory_id = trajectory_id
        self._history: list[dict[str, Any]] = []
        self._steps: list[dict[str, Any]] = []
        self._info: dict[str, Any] = {
            "exit_status": "running",
            "submission": None,
            "model_stats": {
                "instance_cost": None,
                "tokens_sent": None,
                "tokens_received": None,
                "api_calls": None,
            },
        }
        self._flush_every = max(1, flush_every)
        self._step_since_flush = 0
        if system_prompt:
            self._history.append({"role": "system", "content": system_prompt})

    # ----- public API -----

    def user_message(self, content: str) -> None:
        """Add the user's problem statement / initial prompt."""
        self._history.append({"role": "user", "content": content})
        self._flush(force=True)

    def step(
        self,
        *,
        thought: str = "",
        action: str = "",
        observation: str = "",
        response: str = "",
    ) -> None:
        self._steps.append(
            {
                "thought": thought,
                "action": action,
                "response": response,
                "observation": observation,
                "messages": [],
            }
        )
        self._step_since_flush += 1
        if self._step_since_flush >= self._flush_every:
            self._flush()

    def finish(
        self,
        *,
        exit_status: str = "submitted",
        submission: Optional[str] = None,
        eval: Optional[EvalState] = None,
        instance_cost: Optional[float] = None,
        tokens_sent: Optional[int] = None,
        tokens_received: Optional[int] = None,
        api_calls: Optional[int] = None,
    ) -> dict[str, Any]:
        self._info["exit_status"] = exit_status
        if submission is not None:
            self._info["submission"] = submission
        stats = self._info["model_stats"]
        if instance_cost is not None:
            stats["instance_cost"] = instance_cost
        if tokens_sent is not None:
            stats["tokens_sent"] = tokens_sent
        if tokens_received is not None:
            stats["tokens_received"] = tokens_received
        if api_calls is not None:
            stats["api_calls"] = api_calls
        elif stats.get("api_calls") is None:
            stats["api_calls"] = len(self._steps)
        return self._flush(force=True, eval=eval)

    # ----- internals -----

    def _payload(self) -> dict[str, Any]:
        return {
            "history": self._history,
            "trajectory": self._steps,
            "info": self._info,
        }

    def _flush(self, *, force: bool = False, eval: Optional[EvalState] = None) -> dict[str, Any]:
        if not force and self._step_since_flush == 0:
            return {}
        result = self._client.ingest(
            self.run_id,
            self.trajectory_id,
            self._payload(),
            eval=eval,
        )
        self._step_since_flush = 0
        return result


@contextmanager
def attach(
    run_id: str,
    trajectory_id: str,
    *,
    base_url: str = "http://localhost:8080",
    author: Optional[str] = None,
    system_prompt: Optional[str] = None,
    flush_every: int = 1,
    client: Optional[StudioClient] = None,
) -> Iterator[TrajectoryContext]:
    """Attach the SDK to an agent run. Use as a context manager."""
    own_client = client is None
    studio = client or StudioClient(base_url=base_url, author=author)
    try:
        ctx = TrajectoryContext(
            studio,
            run_id,
            trajectory_id,
            system_prompt=system_prompt,
            flush_every=flush_every,
        )
        yield ctx
    finally:
        if own_client:
            studio.close()
