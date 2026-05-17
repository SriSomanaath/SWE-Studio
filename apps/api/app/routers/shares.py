from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header

from app import shares as svc
from app.schemas import ResolvedShare, Share, ShareCreate

router = APIRouter(tags=["shares"])

AuthorHeader = Annotated[str | None, Header(alias="X-Author")]


@router.get("/shares", response_model=list[Share])
def list_shares() -> list[Share]:
    return svc.list_shares()


@router.post("/shares", response_model=Share, status_code=201)
def post_share(payload: ShareCreate, x_author: AuthorHeader = None) -> Share:
    return svc.create_share(
        kind=payload.kind,
        run_id=payload.run_id,
        trajectory_id=payload.trajectory_id,
        slug=payload.slug,
        description=payload.description,
        ttl_seconds=payload.ttl_seconds,
        author=x_author,
    )


@router.get("/shares/{token}/resolve", response_model=ResolvedShare)
def resolve_share(token: str) -> ResolvedShare:
    """Public — anyone with the token can open it."""
    return svc.resolve(token)


@router.delete("/shares/{token}", status_code=204)
def delete_share(token: str) -> None:
    svc.revoke_share(token)
