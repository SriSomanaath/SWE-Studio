"""Workspaces + user identity.

Single-tenant local-dev mode still works without auth — every write is owned
by the `default` workspace, seeded automatically by `db.initialize()`.

When a real user signs in through the web (NextAuth → `X-Studio-User` /
`X-Studio-Email`), the API auto-provisions a row in `users` and a personal
workspace named after them on first contact. Future phases can add invites
and shared workspaces on top of this scaffolding.
"""

from __future__ import annotations

import re
import time

from fastapi import HTTPException

from app import db
from app.schemas import CurrentUser, User, Workspace

DEFAULT_WORKSPACE_ID = db.DEFAULT_WORKSPACE_ID

_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


def _row_to_workspace(row: object) -> Workspace:
    return Workspace.model_validate(dict(row))  # type: ignore[arg-type]


def _row_to_user(row: object) -> User:
    return User.model_validate(dict(row))  # type: ignore[arg-type]


def get_workspace(workspace_id: str) -> Workspace:
    row = db.fetch_one(
        "SELECT id, name, description, created_at FROM workspaces WHERE id = ?",
        (workspace_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Workspace '{workspace_id}' not found")
    return _row_to_workspace(row)


def list_workspaces_for_user(user_id: str | None) -> list[Workspace]:
    """Return all workspaces this user is a member of, falling back to the
    default workspace when the user isn't signed in or has no memberships."""
    rows: list[object] = []
    if user_id:
        rows = db.fetch_all(
            """
            SELECT w.id, w.name, w.description, w.created_at
            FROM workspaces w
            JOIN workspace_members m ON m.workspace_id = w.id
            WHERE m.user_id = ?
            ORDER BY w.created_at ASC
            """,
            (user_id,),
        )
    if not rows:
        rows = db.fetch_all(
            "SELECT id, name, description, created_at FROM workspaces WHERE id = ?",
            (DEFAULT_WORKSPACE_ID,),
        )
    return [_row_to_workspace(r) for r in rows]


def list_workspaces() -> list[Workspace]:
    return [
        _row_to_workspace(r)
        for r in db.fetch_all(
            "SELECT id, name, description, created_at FROM workspaces ORDER BY created_at ASC"
        )
    ]


def create_workspace(
    workspace_id: str, name: str, description: str | None, owner_id: str | None
) -> Workspace:
    if not _ID_RE.match(workspace_id):
        raise HTTPException(status_code=400, detail="workspace id must be lowercase kebab-case")
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if len(name) > 80:
        raise HTTPException(status_code=400, detail="name too long")
    desc = (description or "").strip()[:300] or None
    now = time.time()
    with db.write_tx() as conn:
        existing = conn.execute(
            "SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="workspace id already in use")
        conn.execute(
            "INSERT INTO workspaces (id, name, description, created_at) VALUES (?, ?, ?, ?)",
            (workspace_id, name, desc, now),
        )
        if owner_id:
            # Provision the user first — workspace_members has a FK on users.
            conn.execute(
                """
                INSERT INTO users (id, name, email, created_at)
                VALUES (?, NULL, NULL, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (owner_id, now),
            )
            conn.execute(
                """
                INSERT INTO workspace_members (workspace_id, user_id, role, created_at)
                VALUES (?, ?, 'owner', ?)
                ON CONFLICT(workspace_id, user_id) DO NOTHING
                """,
                (workspace_id, owner_id, now),
            )
    return get_workspace(workspace_id)


def upsert_user(user_id: str, *, name: str | None, email: str | None) -> User:
    """Auto-provision a user row when an authenticated request first lands.
    Also adds them to the default workspace so they immediately see data."""
    now = time.time()
    with db.write_tx() as conn:
        conn.execute(
            """
            INSERT INTO users (id, name, email, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = COALESCE(excluded.name, users.name),
                email = COALESCE(excluded.email, users.email)
            """,
            (user_id, name, email, now),
        )
        conn.execute(
            """
            INSERT INTO workspace_members (workspace_id, user_id, role, created_at)
            VALUES (?, ?, 'member', ?)
            ON CONFLICT(workspace_id, user_id) DO NOTHING
            """,
            (DEFAULT_WORKSPACE_ID, user_id, now),
        )
    row = db.fetch_one(
        "SELECT id, name, email, created_at FROM users WHERE id = ?", (user_id,)
    )
    return _row_to_user(row)  # type: ignore[arg-type]


def current_user(
    user_id: str | None,
    name: str | None,
    email: str | None,
    workspace_hint: str | None,
) -> CurrentUser:
    """`GET /me` builder. Auto-provisions when an authenticated header is present."""
    user: User | None = None
    if user_id:
        user = upsert_user(user_id, name=name, email=email)
    workspaces = list_workspaces_for_user(user_id)
    active = workspace_hint if workspace_hint and any(w.id == workspace_hint for w in workspaces) else workspaces[0].id
    return CurrentUser(user=user, workspaces=workspaces, active_workspace_id=active)
