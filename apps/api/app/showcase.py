"""Showcase service — curated trajectory permalinks."""

from __future__ import annotations

import re
import sqlite3
import time

from fastapi import HTTPException

from app import db
from app.schemas import ShowcaseEntry

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


def _validate_slug(slug: str) -> str:
    slug = slug.strip().lower()
    if not _SLUG_RE.match(slug):
        raise HTTPException(
            status_code=400,
            detail="slug must be lowercase, kebab-case, 1–64 chars (a–z, 0–9, hyphen)",
        )
    return slug


def _ensure_trajectory(run_id: str, trajectory_id: str) -> None:
    row = db.fetch_one(
        "SELECT 1 FROM trajectories WHERE run_id = ? AND id = ?",
        (run_id, trajectory_id),
    )
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Trajectory '{trajectory_id}' not found in run '{run_id}'",
        )


def _validate_pinned_step(run_id: str, trajectory_id: str, pinned_step: int | None) -> int | None:
    if pinned_step is None:
        return None
    row = db.fetch_one(
        "SELECT step_count FROM trajectories WHERE run_id = ? AND id = ?",
        (run_id, trajectory_id),
    )
    if not row:
        return None  # shouldn't happen, _ensure_trajectory ran already
    step_count = int(row["step_count"] or 0)
    if pinned_step < 0 or pinned_step >= step_count:
        raise HTTPException(
            status_code=400,
            detail=f"pinned_step must be 0–{step_count - 1}",
        )
    return pinned_step


def _row_to_entry(row: sqlite3.Row) -> ShowcaseEntry:
    return ShowcaseEntry.model_validate(dict(row))


def list_showcase() -> list[ShowcaseEntry]:
    rows = db.fetch_all(
        """
        SELECT slug, run_id, trajectory_id, title, description, pinned_step,
               author, created_at, updated_at
        FROM showcase
        ORDER BY created_at DESC
        """
    )
    return [_row_to_entry(r) for r in rows]


def get_showcase(slug: str) -> ShowcaseEntry:
    slug = slug.strip().lower()
    row = db.fetch_one(
        """
        SELECT slug, run_id, trajectory_id, title, description, pinned_step,
               author, created_at, updated_at
        FROM showcase WHERE slug = ?
        """,
        (slug,),
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Showcase '{slug}' not found")
    return _row_to_entry(row)


def create_showcase(
    *,
    slug: str,
    run_id: str,
    trajectory_id: str,
    title: str,
    description: str | None,
    pinned_step: int | None,
    author: str | None,
) -> ShowcaseEntry:
    slug = _validate_slug(slug)
    title = title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="title cannot be empty")
    if len(title) > 200:
        raise HTTPException(status_code=400, detail="title too long (max 200)")
    description = (description or "").strip()[:1000] or None

    _ensure_trajectory(run_id, trajectory_id)
    pinned_step = _validate_pinned_step(run_id, trajectory_id, pinned_step)

    auth = (author or "").strip()[:64] or "anonymous"
    now = time.time()

    with db.write_tx() as conn:
        existing = conn.execute(
            "SELECT 1 FROM showcase WHERE slug = ?", (slug,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail=f"slug '{slug}' is already in use")
        conn.execute(
            """
            INSERT INTO showcase
                (slug, run_id, trajectory_id, title, description, pinned_step,
                 author, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (slug, run_id, trajectory_id, title, description, pinned_step, auth, now, now),
        )

    return get_showcase(slug)


def update_showcase(
    slug: str,
    *,
    title: str | None = None,
    description: str | None = None,
    pinned_step: int | None = None,
) -> ShowcaseEntry:
    current = get_showcase(slug)
    new_title = (title if title is not None else current.title).strip()
    if not new_title:
        raise HTTPException(status_code=400, detail="title cannot be empty")

    new_desc = description if description is not None else current.description
    if new_desc is not None:
        new_desc = new_desc.strip()[:1000] or None

    new_pinned = pinned_step if pinned_step is not None else current.pinned_step
    new_pinned = _validate_pinned_step(current.run_id, current.trajectory_id, new_pinned)

    now = time.time()
    with db.write_tx() as conn:
        conn.execute(
            """
            UPDATE showcase
            SET title = ?, description = ?, pinned_step = ?, updated_at = ?
            WHERE slug = ?
            """,
            (new_title, new_desc, new_pinned, now, current.slug),
        )

    return get_showcase(slug)


def delete_showcase(slug: str) -> None:
    slug = _validate_slug(slug)
    with db.write_tx() as conn:
        cur = conn.execute("DELETE FROM showcase WHERE slug = ?", (slug,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Showcase '{slug}' not found")
