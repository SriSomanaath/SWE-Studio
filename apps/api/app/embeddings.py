"""Local sentence-embedding similarity, optional.

When `sentence-transformers` is installed, the indexer computes a vector per
trajectory (from its problem statement + flattened action text) and stores it
in the `embeddings` table. `/similar` then ranks peers by cosine similarity
instead of falling back to Phase 9's FTS5-bm25 approach.

If the dep is missing, every entry point degrades cleanly — calls return empty
results and `/embeddings/status` reports `available: false` with a hint.
"""

from __future__ import annotations

import logging
import struct
import threading
import time
from functools import lru_cache
from typing import Any

from app import db
from app.config import settings

logger = logging.getLogger(__name__)

_DTYPE_FMT = "<f"  # little-endian float32; one per dimension.
_CACHE_LOCK = threading.Lock()


def _pack(vec: list[float]) -> bytes:
    return b"".join(struct.pack(_DTYPE_FMT, v) for v in vec)


def _unpack(blob: bytes) -> list[float]:
    n = len(blob) // 4
    return list(struct.unpack(f"<{n}f", blob))


# --- Encoder ---------------------------------------------------------------


class _EncoderState:
    model: Any | None = None
    error: str | None = None
    name: str = settings.embedding_model
    dim: int = 0


_state = _EncoderState()


def _load_encoder() -> Any | None:
    """Lazy-load sentence-transformers. Cache for the process lifetime."""
    with _CACHE_LOCK:
        if _state.model is not None or _state.error is not None:
            return _state.model
        try:
            from sentence_transformers import SentenceTransformer  # noqa: WPS433
        except ImportError as exc:
            _state.error = f"sentence-transformers not installed: {exc}"
            logger.info("Embeddings disabled — install with `pip install sentence-transformers`")
            return None
        try:
            _state.model = SentenceTransformer(_state.name)
            _state.dim = int(_state.model.get_sentence_embedding_dimension())
            logger.info("Embeddings ready — model=%s dim=%d", _state.name, _state.dim)
        except Exception as exc:  # noqa: BLE001
            _state.error = f"model load failed: {exc}"
            logger.warning("Embedding model load failed: %s", exc)
            return None
        return _state.model


def is_available() -> bool:
    return _load_encoder() is not None


def status_payload() -> dict[str, Any]:
    available = is_available()
    indexed = db.fetch_one("SELECT COUNT(*) AS n FROM embeddings")
    return {
        "available": available,
        "model": _state.name,
        "indexed_count": int(indexed["n"]) if indexed else 0,
        "reason": None if available else _state.error,
    }


def encode_one(text: str) -> list[float] | None:
    encoder = _load_encoder()
    if encoder is None:
        return None
    vec = encoder.encode(text, normalize_embeddings=True)
    return [float(x) for x in vec]


# --- Indexer hook ----------------------------------------------------------


def upsert_for_trajectory(
    run_id: str,
    trajectory_id: str,
    *,
    problem: str,
    action_text: str,
) -> None:
    """Called from the indexer after a trajectory is written. Silent no-op
    when embeddings aren't available so the base indexer never depends on
    the optional model."""
    encoder = _load_encoder()
    if encoder is None:
        return
    text = (problem + "\n" + action_text).strip()
    if not text:
        return
    vec = encoder.encode(text, normalize_embeddings=True)
    blob = _pack([float(x) for x in vec])
    dim = len(vec)
    with db.write_tx() as conn:
        conn.execute(
            """
            INSERT INTO embeddings (run_id, trajectory_id, model, vec, dim, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, trajectory_id, model) DO UPDATE SET
                vec = excluded.vec,
                dim = excluded.dim,
                created_at = excluded.created_at
            """,
            (run_id, trajectory_id, _state.name, blob, dim, time.time()),
        )


def drop_for_trajectory(run_id: str, trajectory_id: str) -> None:
    with db.write_tx() as conn:
        conn.execute(
            "DELETE FROM embeddings WHERE run_id = ? AND trajectory_id = ?",
            (run_id, trajectory_id),
        )


# --- Query layer -----------------------------------------------------------


def _cosine(a: list[float], b: list[float]) -> float:
    # Vectors are normalized at encode time, so cosine reduces to dot.
    return sum(x * y for x, y in zip(a, b, strict=False))


def find_similar(
    run_id: str,
    trajectory_id: str,
    limit: int = 10,
) -> list[tuple[str, str, float]]:
    """Return `(run_id, trajectory_id, score)` for top-N nearest peers.

    Empty list when no embeddings exist (caller should fall back to FTS5).
    """
    src_row = db.fetch_one(
        "SELECT vec, model FROM embeddings WHERE run_id = ? AND trajectory_id = ? "
        "ORDER BY created_at DESC LIMIT 1",
        (run_id, trajectory_id),
    )
    if not src_row:
        return []

    src_vec = _unpack(src_row["vec"])
    rows = db.fetch_all(
        "SELECT run_id, trajectory_id, vec FROM embeddings WHERE model = ? "
        "AND NOT (run_id = ? AND trajectory_id = ?)",
        (src_row["model"], run_id, trajectory_id),
    )
    scored: list[tuple[str, str, float]] = []
    for r in rows:
        v = _unpack(r["vec"])
        if len(v) != len(src_vec):
            continue
        scored.append((r["run_id"], r["trajectory_id"], _cosine(src_vec, v)))
    scored.sort(key=lambda t: -t[2])
    return scored[:limit]


@lru_cache(maxsize=1)
def _has_any_embeddings_cached() -> bool:
    row = db.fetch_one("SELECT 1 FROM embeddings LIMIT 1")
    return row is not None


def has_any_embeddings() -> bool:
    # Don't actually cache — index churn would make it stale. Keep the lru
    # signature for the symmetric API but bypass the cache.
    row = db.fetch_one("SELECT 1 FROM embeddings LIMIT 1")
    return row is not None
