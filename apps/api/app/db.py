"""SQLite metadata index.

We never store step content here — that stays in `.traj` files. SQLite is a
purely derived view that exists to make list/filter/sort queries cheap.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS runs (
    id              TEXT PRIMARY KEY,
    relative_path   TEXT NOT NULL,
    has_results     INTEGER NOT NULL DEFAULT 0,
    indexed_at      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS trajectories (
    run_id              TEXT NOT NULL,
    id                  TEXT NOT NULL,
    file_path           TEXT NOT NULL,
    relative_path       TEXT NOT NULL,
    mtime               REAL NOT NULL,

    exit_status         TEXT,
    api_calls           INTEGER,
    instance_cost       REAL,
    tokens_sent         INTEGER,
    tokens_received     INTEGER,
    step_count          INTEGER NOT NULL DEFAULT 0,

    eval_completed      INTEGER,
    eval_submitted      INTEGER,
    eval_resolved       INTEGER,

    problem_statement   TEXT,

    PRIMARY KEY (run_id, id),
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_traj_run_id        ON trajectories(run_id);
CREATE INDEX IF NOT EXISTS ix_traj_eval_resolved ON trajectories(eval_resolved);
CREATE INDEX IF NOT EXISTS ix_traj_exit_status   ON trajectories(exit_status);
CREATE INDEX IF NOT EXISTS ix_traj_instance_cost ON trajectories(instance_cost);
CREATE INDEX IF NOT EXISTS ix_traj_step_count    ON trajectories(step_count);

CREATE TABLE IF NOT EXISTS annotations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    trajectory_id   TEXT NOT NULL,
    step_index      INTEGER NOT NULL,   -- -1 means trajectory-level
    author          TEXT NOT NULL,
    body            TEXT NOT NULL,
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL,
    FOREIGN KEY (run_id, trajectory_id)
        REFERENCES trajectories(run_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_annot_target ON annotations(run_id, trajectory_id, step_index);

CREATE TABLE IF NOT EXISTS bookmarks (
    run_id          TEXT NOT NULL,
    trajectory_id   TEXT NOT NULL,
    author          TEXT NOT NULL,
    note            TEXT,
    created_at      REAL NOT NULL,
    PRIMARY KEY (run_id, trajectory_id, author),
    FOREIGN KEY (run_id, trajectory_id)
        REFERENCES trajectories(run_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_bookmark_author ON bookmarks(author);

CREATE VIRTUAL TABLE IF NOT EXISTS trajectories_fts USING fts5(
    run_id UNINDEXED,
    trajectory_id UNINDEXED,
    instance_id,
    problem,
    step_text,
    tokenize = 'porter unicode61 remove_diacritics 1'
);

CREATE VIRTUAL TABLE IF NOT EXISTS annotations_fts USING fts5(
    annotation_id UNINDEXED,
    run_id UNINDEXED,
    trajectory_id UNINDEXED,
    step_index UNINDEXED,
    body,
    tokenize = 'porter unicode61 remove_diacritics 1'
);

CREATE TABLE IF NOT EXISTS showcase (
    slug            TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL,
    trajectory_id   TEXT NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT,
    pinned_step     INTEGER,
    author          TEXT NOT NULL,
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL,
    FOREIGN KEY (run_id, trajectory_id)
        REFERENCES trajectories(run_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_showcase_created ON showcase(created_at DESC);

CREATE TABLE IF NOT EXISTS summaries (
    run_id          TEXT NOT NULL,
    trajectory_id   TEXT NOT NULL,
    provider        TEXT NOT NULL,
    body            TEXT NOT NULL,
    model           TEXT,
    created_at      REAL NOT NULL,
    PRIMARY KEY (run_id, trajectory_id, provider),
    FOREIGN KEY (run_id, trajectory_id)
        REFERENCES trajectories(run_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS webhooks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url             TEXT NOT NULL,
    events          TEXT NOT NULL,   -- JSON array of event names; empty array = all
    secret          TEXT NOT NULL,
    active          INTEGER NOT NULL DEFAULT 1,
    description     TEXT,
    created_at      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    webhook_id      INTEGER NOT NULL,
    event           TEXT NOT NULL,
    payload         TEXT NOT NULL,
    status_code     INTEGER,
    success         INTEGER NOT NULL,
    attempts        INTEGER NOT NULL DEFAULT 1,
    error           TEXT,
    created_at      REAL NOT NULL,
    FOREIGN KEY (webhook_id) REFERENCES webhooks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_webhook_deliveries_recent
    ON webhook_deliveries(webhook_id, created_at DESC);

CREATE TABLE IF NOT EXISTS shares (
    token           TEXT PRIMARY KEY,
    kind            TEXT NOT NULL,     -- 'run' | 'trajectory' | 'showcase'
    target_run_id   TEXT,
    target_traj_id  TEXT,
    target_slug     TEXT,
    description     TEXT,
    author          TEXT NOT NULL,
    created_at      REAL NOT NULL,
    expires_at      REAL,              -- NULL = never expires
    revoked         INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_shares_created ON shares(created_at DESC);

CREATE TABLE IF NOT EXISTS embeddings (
    run_id          TEXT NOT NULL,
    trajectory_id   TEXT NOT NULL,
    model           TEXT NOT NULL,
    vec             BLOB NOT NULL,
    dim             INTEGER NOT NULL,
    created_at      REAL NOT NULL,
    PRIMARY KEY (run_id, trajectory_id, model),
    FOREIGN KEY (run_id, trajectory_id)
        REFERENCES trajectories(run_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workspaces (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT,
    created_at      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    name            TEXT,
    email           TEXT,
    created_at      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS workspace_members (
    workspace_id    TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'owner',
    created_at      REAL NOT NULL,
    PRIMARY KEY (workspace_id, user_id),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_workspace_members_user ON workspace_members(user_id);
"""

CURRENT_SCHEMA_VERSION = 8

DEFAULT_WORKSPACE_ID = "default"

_write_lock = threading.Lock()


def _db_path() -> Path:
    p = settings.db_path
    return p.resolve()


def _ensure_parent(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def connect() -> sqlite3.Connection:
    """Open a connection with sensible defaults.

    Each caller gets its own connection (SQLite is thread-friendly when each
    thread has its own connection). WAL mode lets readers and the writer
    coexist without blocking each other.
    """
    path = _db_path()
    _ensure_parent(path)
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize() -> None:
    """Create tables if missing and stamp the schema version."""
    import time

    with _write_lock, connect() as conn:
        conn.executescript(SCHEMA)
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (CURRENT_SCHEMA_VERSION,),
            )
        elif row["version"] < CURRENT_SCHEMA_VERSION:
            conn.execute(
                "UPDATE schema_version SET version = ?",
                (CURRENT_SCHEMA_VERSION,),
            )

        # Always ensure the default workspace exists so single-tenant local
        # installs keep working without any user setup.
        seeded = conn.execute(
            "SELECT 1 FROM workspaces WHERE id = ?", (DEFAULT_WORKSPACE_ID,)
        ).fetchone()
        if seeded is None:
            conn.execute(
                "INSERT INTO workspaces (id, name, description, created_at) VALUES (?, ?, ?, ?)",
                (
                    DEFAULT_WORKSPACE_ID,
                    "Personal workspace",
                    "Auto-created on first start. Owns all data when nobody is authenticated.",
                    time.time(),
                ),
            )


def reset() -> None:
    """Drop and recreate everything. Used by tests."""
    with _write_lock, connect() as conn:
        conn.executescript(
            "DROP TABLE IF EXISTS workspace_members;"
            "DROP TABLE IF EXISTS users;"
            "DROP TABLE IF EXISTS workspaces;"
            "DROP TABLE IF EXISTS embeddings;"
            "DROP TABLE IF EXISTS shares;"
            "DROP TABLE IF EXISTS webhook_deliveries;"
            "DROP TABLE IF EXISTS webhooks;"
            "DROP TABLE IF EXISTS summaries;"
            "DROP TABLE IF EXISTS showcase;"
            "DROP TABLE IF EXISTS annotations_fts;"
            "DROP TABLE IF EXISTS trajectories_fts;"
            "DROP TABLE IF EXISTS annotations;"
            "DROP TABLE IF EXISTS bookmarks;"
            "DROP TABLE IF EXISTS trajectories;"
            "DROP TABLE IF EXISTS runs;"
            "DROP TABLE IF EXISTS schema_version;"
        )
    initialize()


@contextmanager
def write_tx() -> Iterator[sqlite3.Connection]:
    """Serialize all writes through one connection + lock.

    SQLite handles concurrent reads fine but at most one writer can hold the
    write lock. We funnel writes through a single Python lock so retries are
    rare and we get predictable behavior under watchfiles event bursts.
    """
    with _write_lock:
        conn = connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()


def fetch_all(sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    conn = connect()
    try:
        return list(conn.execute(sql, params).fetchall())
    finally:
        conn.close()


def fetch_one(sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    conn = connect()
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()
