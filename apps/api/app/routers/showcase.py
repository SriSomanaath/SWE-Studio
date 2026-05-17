from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header

from app import showcase as svc
from app.schemas import ShowcaseCreate, ShowcaseEntry, ShowcaseUpdate

router = APIRouter(prefix="/showcase", tags=["showcase"])

AuthorHeader = Annotated[str | None, Header(alias="X-Author")]


@router.get("", response_model=list[ShowcaseEntry])
def list_showcase() -> list[ShowcaseEntry]:
    return svc.list_showcase()


@router.get("/{slug}", response_model=ShowcaseEntry)
def get_showcase(slug: str) -> ShowcaseEntry:
    return svc.get_showcase(slug)


@router.post("", response_model=ShowcaseEntry, status_code=201)
def create_showcase(payload: ShowcaseCreate, x_author: AuthorHeader = None) -> ShowcaseEntry:
    return svc.create_showcase(
        slug=payload.slug,
        run_id=payload.run_id,
        trajectory_id=payload.trajectory_id,
        title=payload.title,
        description=payload.description,
        pinned_step=payload.pinned_step,
        author=x_author,
    )


@router.patch("/{slug}", response_model=ShowcaseEntry)
def update_showcase(slug: str, payload: ShowcaseUpdate) -> ShowcaseEntry:
    return svc.update_showcase(
        slug,
        title=payload.title,
        description=payload.description,
        pinned_step=payload.pinned_step,
    )


@router.delete("/{slug}", status_code=204)
def delete_showcase(slug: str) -> None:
    svc.delete_showcase(slug)
