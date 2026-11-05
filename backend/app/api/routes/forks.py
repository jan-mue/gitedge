"""Repository fork routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.api.dependencies import CurrentUser, ForkServiceDep, OptionalRepositoryUser
from app.api.permissions import require_permission, token_authentication
from app.entities.users import User
from app.schemas.social import ForkCreate, ForkPublic, ForksPublic

router = APIRouter(prefix="/repositories", tags=["forks"])


@router.get("/{owner}/{repo}/forks")
async def list_forks(
    request: Request,
    owner: str,
    repo: str,
    fork_service: ForkServiceDep,
    current_user: Annotated[
        User | None,
        Depends(require_permission("repository:read", user_dep=OptionalRepositoryUser)),
    ],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=0)] = 100,
) -> ForksPublic:
    """List forks of a repository."""
    authenticated = token_authentication(request)
    allowed_ids = (
        [UUID(repository_id) for repository_id in authenticated.token.repository_ids]
        if authenticated is not None
        else None
    )
    return await fork_service.list_forks(owner, repo, offset, limit, current_user, allowed_repository_ids=allowed_ids)


@router.post("/{owner}/{repo}/forks", status_code=201)
async def fork_repository(
    owner: str,
    repo: str,
    body: ForkCreate,
    fork_service: ForkServiceDep,
    current_user: Annotated[User, Depends(require_permission("repository:fork", user_dep=CurrentUser))],
) -> ForkPublic:
    """Fork a repository."""
    return await fork_service.fork(owner, repo, body, current_user)
