"""In-memory presence tracking for collaborative annotation.

Viewers ping `POST /runs/{r}/trajectories/{t}/presence` with their step
index. We keep a per-channel dict of `(user_id → Viewer)` records with a
sliding TTL; anyone subscribed to the corresponding SSE channel receives
the updated viewer list whenever it changes.

This is deliberately not persisted to SQLite — presence is ephemeral and
should not survive an API restart.
"""

from __future__ import annotations

import threading
import time

from app.schemas import PresenceState, Viewer
from app.streaming import bus

_TTL = 30.0  # seconds before a viewer is considered gone
_lock = threading.Lock()
_state: dict[tuple[str, str], dict[str, Viewer]] = {}


def _channel(run_id: str, trajectory_id: str) -> str:
    return f"presence:{run_id}:{trajectory_id}"


def _prune(viewers: dict[str, Viewer]) -> dict[str, Viewer]:
    cutoff = time.time() - _TTL
    return {uid: v for uid, v in viewers.items() if v.last_seen >= cutoff}


def upsert(
    run_id: str,
    trajectory_id: str,
    user_id: str,
    name: str | None,
    step_index: int | None,
) -> PresenceState:
    key = (run_id, trajectory_id)
    now = time.time()
    with _lock:
        viewers = _prune(_state.get(key, {}))
        viewers[user_id] = Viewer(
            user_id=user_id,
            name=name,
            step_index=step_index,
            last_seen=now,
        )
        _state[key] = viewers
        snapshot = list(viewers.values())

    state = PresenceState(
        run_id=run_id,
        trajectory_id=trajectory_id,
        viewers=sorted(snapshot, key=lambda v: v.last_seen, reverse=True),
    )
    bus.publish(
        _channel(run_id, trajectory_id),
        {"type": "presence", **state.model_dump()},
    )
    return state


def remove(run_id: str, trajectory_id: str, user_id: str) -> PresenceState:
    key = (run_id, trajectory_id)
    with _lock:
        viewers = _prune(_state.get(key, {}))
        viewers.pop(user_id, None)
        _state[key] = viewers
        snapshot = list(viewers.values())

    state = PresenceState(
        run_id=run_id,
        trajectory_id=trajectory_id,
        viewers=sorted(snapshot, key=lambda v: v.last_seen, reverse=True),
    )
    bus.publish(
        _channel(run_id, trajectory_id),
        {"type": "presence", **state.model_dump()},
    )
    return state


def snapshot(run_id: str, trajectory_id: str) -> PresenceState:
    key = (run_id, trajectory_id)
    with _lock:
        viewers = _prune(_state.get(key, {}))
        _state[key] = viewers
        snapshot = list(viewers.values())
    return PresenceState(
        run_id=run_id,
        trajectory_id=trajectory_id,
        viewers=sorted(snapshot, key=lambda v: v.last_seen, reverse=True),
    )


def channel(run_id: str, trajectory_id: str) -> str:
    return _channel(run_id, trajectory_id)
