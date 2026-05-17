"""Annotation + bookmark routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Query

from app import annotations as svc
from app.schemas import (
    Annotation,
    AnnotationCreate,
    AnnotationUpdate,
    Bookmark,
    BookmarkCreate,
)

router = APIRouter(tags=["notes"])

AuthorHeader = Annotated[str | None, Header(alias="X-Author")]


@router.get(
    "/runs/{run_id}/trajectories/{trajectory_id}/annotations",
    response_model=list[Annotation],
)
def get_annotations(run_id: str, trajectory_id: str) -> list[Annotation]:
    return svc.list_annotations(run_id, trajectory_id)


@router.post(
    "/runs/{run_id}/trajectories/{trajectory_id}/annotations",
    response_model=Annotation,
    status_code=201,
)
def post_annotation(
    run_id: str,
    trajectory_id: str,
    payload: AnnotationCreate,
    x_author: AuthorHeader = None,
) -> Annotation:
    return svc.create_annotation(
        run_id, trajectory_id, payload.step_index, payload.body, x_author
    )


@router.patch("/annotations/{annotation_id}", response_model=Annotation)
def patch_annotation(
    annotation_id: int,
    payload: AnnotationUpdate,
    x_author: AuthorHeader = None,
) -> Annotation:
    return svc.update_annotation(annotation_id, payload.body, x_author)


@router.delete("/annotations/{annotation_id}", status_code=204)
def delete_annotation(annotation_id: int) -> None:
    svc.delete_annotation(annotation_id)


@router.get("/bookmarks", response_model=list[Bookmark])
def get_bookmarks(
    author: Annotated[str | None, Query()] = None,
) -> list[Bookmark]:
    return svc.list_bookmarks(author)


@router.put(
    "/bookmarks/{run_id}/{trajectory_id}",
    response_model=Bookmark,
)
def put_bookmark(
    run_id: str,
    trajectory_id: str,
    payload: BookmarkCreate,
    x_author: AuthorHeader = None,
) -> Bookmark:
    return svc.upsert_bookmark(run_id, trajectory_id, x_author, payload.note)


@router.delete("/bookmarks/{run_id}/{trajectory_id}", status_code=204)
def remove_bookmark(
    run_id: str,
    trajectory_id: str,
    x_author: AuthorHeader = None,
) -> None:
    svc.delete_bookmark(run_id, trajectory_id, x_author)
