from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header

from app import workspaces as svc
from app.schemas import CurrentUser, Workspace, WorkspaceCreate

router = APIRouter(tags=["workspaces"])

UserHeader = Annotated[str | None, Header(alias="X-Studio-User")]
NameHeader = Annotated[str | None, Header(alias="X-Studio-Name")]
EmailHeader = Annotated[str | None, Header(alias="X-Studio-Email")]
WorkspaceHeader = Annotated[str | None, Header(alias="X-Studio-Workspace")]


@router.get("/me", response_model=CurrentUser)
def get_me(
    x_studio_user: UserHeader = None,
    x_studio_name: NameHeader = None,
    x_studio_email: EmailHeader = None,
    x_studio_workspace: WorkspaceHeader = None,
) -> CurrentUser:
    return svc.current_user(
        user_id=x_studio_user,
        name=x_studio_name,
        email=x_studio_email,
        workspace_hint=x_studio_workspace,
    )


@router.get("/workspaces", response_model=list[Workspace])
def get_workspaces() -> list[Workspace]:
    return svc.list_workspaces()


@router.post("/workspaces", response_model=Workspace, status_code=201)
def post_workspace(
    payload: WorkspaceCreate,
    x_studio_user: UserHeader = None,
) -> Workspace:
    return svc.create_workspace(
        workspace_id=payload.id,
        name=payload.name,
        description=payload.description,
        owner_id=x_studio_user,
    )
