"""Annotation + bookmark service."""

from __future__ import annotations

import time

from fastapi import HTTPException

from app import db
from app.schemas import Annotation, Bookmark

DEFAULT_AUTHOR = "anonymous"


def _author_or_default(author: str | None) -> str:
    if not author:
        return DEFAULT_AUTHOR
    return author.strip()[:64] or DEFAULT_AUTHOR


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


def list_annotations(run_id: str, trajectory_id: str) -> list[Annotation]:
    _ensure_trajectory(run_id, trajectory_id)
    rows = db.fetch_all(
        """
        SELECT id, run_id, trajectory_id, step_index, author, body,
               created_at, updated_at
        FROM annotations
        WHERE run_id = ? AND trajectory_id = ?
        ORDER BY step_index ASC, created_at ASC
        """,
        (run_id, trajectory_id),
    )
    return [Annotation.model_validate(dict(r)) for r in rows]


def create_annotation(
    run_id: str,
    trajectory_id: str,
    step_index: int,
    body: str,
    author: str | None,
) -> Annotation:
    _ensure_trajectory(run_id, trajectory_id)
    body = body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="Annotation body cannot be empty")
    if len(body) > 8000:
        raise HTTPException(status_code=400, detail="Annotation too long (max 8000 chars)")
    now = time.time()
    auth = _author_or_default(author)
    with db.write_tx() as conn:
        cur = conn.execute(
            """
            INSERT INTO annotations
                (run_id, trajectory_id, step_index, author, body, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, trajectory_id, step_index, auth, body, now, now),
        )
        new_id = cur.lastrowid
        conn.execute(
            """
            INSERT INTO annotations_fts
                (annotation_id, run_id, trajectory_id, step_index, body)
            VALUES (?, ?, ?, ?, ?)
            """,
            (new_id, run_id, trajectory_id, step_index, body),
        )
    return Annotation(
        id=new_id,  # type: ignore[arg-type]
        run_id=run_id,
        trajectory_id=trajectory_id,
        step_index=step_index,
        author=auth,
        body=body,
        created_at=now,
        updated_at=now,
    )


def update_annotation(annotation_id: int, body: str, author: str | None) -> Annotation:
    row = db.fetch_one("SELECT * FROM annotations WHERE id = ?", (annotation_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Annotation not found")
    body = body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="Annotation body cannot be empty")
    auth = _author_or_default(author)
    if row["author"] != auth:
        # Phase 5 trust model: any author can edit (no auth). We log the new
        # author but keep the original for attribution.
        pass
    now = time.time()
    with db.write_tx() as conn:
        conn.execute(
            "UPDATE annotations SET body = ?, updated_at = ? WHERE id = ?",
            (body, now, annotation_id),
        )
        conn.execute(
            "DELETE FROM annotations_fts WHERE annotation_id = ?", (annotation_id,)
        )
        conn.execute(
            """
            INSERT INTO annotations_fts
                (annotation_id, run_id, trajectory_id, step_index, body)
            VALUES (?, ?, ?, ?, ?)
            """,
            (annotation_id, row["run_id"], row["trajectory_id"], row["step_index"], body),
        )
    return Annotation(
        id=annotation_id,
        run_id=row["run_id"],
        trajectory_id=row["trajectory_id"],
        step_index=row["step_index"],
        author=row["author"],
        body=body,
        created_at=row["created_at"],
        updated_at=now,
    )


def delete_annotation(annotation_id: int) -> None:
    row = db.fetch_one("SELECT 1 FROM annotations WHERE id = ?", (annotation_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Annotation not found")
    with db.write_tx() as conn:
        conn.execute("DELETE FROM annotations WHERE id = ?", (annotation_id,))
        conn.execute(
            "DELETE FROM annotations_fts WHERE annotation_id = ?", (annotation_id,)
        )


def list_bookmarks(author: str | None = None) -> list[Bookmark]:
    if author:
        rows = db.fetch_all(
            "SELECT * FROM bookmarks WHERE author = ? ORDER BY created_at DESC",
            (author,),
        )
    else:
        rows = db.fetch_all("SELECT * FROM bookmarks ORDER BY created_at DESC")
    return [Bookmark.model_validate(dict(r)) for r in rows]


def upsert_bookmark(
    run_id: str,
    trajectory_id: str,
    author: str | None,
    note: str | None,
) -> Bookmark:
    _ensure_trajectory(run_id, trajectory_id)
    auth = _author_or_default(author)
    now = time.time()
    note_clean = (note or "").strip()[:512] or None
    with db.write_tx() as conn:
        conn.execute(
            """
            INSERT INTO bookmarks (run_id, trajectory_id, author, note, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(run_id, trajectory_id, author) DO UPDATE SET
                note = excluded.note
            """,
            (run_id, trajectory_id, auth, note_clean, now),
        )
    return Bookmark(
        run_id=run_id,
        trajectory_id=trajectory_id,
        author=auth,
        note=note_clean,
        created_at=now,
    )


def delete_bookmark(run_id: str, trajectory_id: str, author: str | None) -> None:
    auth = _author_or_default(author)
    with db.write_tx() as conn:
        conn.execute(
            "DELETE FROM bookmarks WHERE run_id = ? AND trajectory_id = ? AND author = ?",
            (run_id, trajectory_id, auth),
        )
