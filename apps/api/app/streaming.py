"""In-process pub/sub for trajectory events.

Producers are the indexer (when a `.traj` file changes) and any future
direct integrations. Consumers are SSE clients hanging off
`/runs/.../events` and `/live`.

Channels:
  - `traj:<run_id>:<traj_id>`  — per-trajectory updates
  - `run:<run_id>`             — per-run summary updates
  - `*`                        — firehose (used by /live)
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any

logger = logging.getLogger(__name__)

# Drop newest events if a subscriber is too slow. 256 is generous for SSE clients.
_QUEUE_MAX = 256


def channel_traj(run_id: str, traj_id: str) -> str:
    return f"traj:{run_id}:{traj_id}"


def channel_run(run_id: str) -> str:
    return f"run:{run_id}"


def channel_firehose() -> str:
    return "*"


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue[dict[str, Any] | None]]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Called from FastAPI lifespan so we can publish from worker threads."""
        self._loop = loop

    def publish(self, channel: str, event: dict[str, Any]) -> None:
        """Thread-safe: dispatches to the bound loop if called off-loop."""
        loop = self._loop
        try:
            current = asyncio.get_running_loop()
        except RuntimeError:
            current = None

        if loop is None or current is loop:
            self._publish_sync(channel, event)
        else:
            loop.call_soon_threadsafe(self._publish_sync, channel, event)

    def _publish_sync(self, channel: str, event: dict[str, Any]) -> None:
        # Per-channel subscribers plus firehose.
        targets = list(self._subs.get(channel, ()))
        targets.extend(self._subs.get(channel_firehose(), ()))
        for q in targets:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Subscriber queue full on %s — dropping event", channel)

    async def stream(self, channel: str) -> AsyncIterator[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=_QUEUE_MAX)
        self._subs[channel].add(q)
        try:
            while True:
                event = await q.get()
                if event is None:
                    break
                yield event
        finally:
            self._subs[channel].discard(q)
            if not self._subs[channel]:
                self._subs.pop(channel, None)


bus = EventBus()
