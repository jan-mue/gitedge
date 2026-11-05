"""Repository fork routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import CurrentUser, ForkServiceDep, OptionalRepositoryUser
from app.api.permissions import require_permission, token_authentication
from app.entities.users import User
from app.schemas.personal_access_tokens import TokenScope
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
        Depends(
            require_permission(
                "repository:read", user_dep=OptionalRepositoryUser, token_scope=TokenScope.REPOSITORY_READ
            )
        ),
    ],
    offset: int = 0,
    limit: int = 100,
) -> ForksPublic:
    """List forks of a repository."""
    result = await fork_service.list_forks(owner, repo, offset, limit, current_user)
    authenticated = token_authentication(request)
    if authenticated is not None:
        result.data = [fork for fork in result.data if str(fork.id) in authenticated.token.repository_ids]
        result.count = len(result.data)
    return result


@router.post("/{owner}/{repo}/forks", status_code=201)
async def fork_repository(
    owner: str,
    repo: str,
    body: ForkCreate,
    fork_service: ForkServiceDep,
    current_user: Annotated[User, Depends(require_permission("repository:read", user_dep=CurrentUser))],
) -> ForkPublic:
    """Fork a repository."""
    return await fork_service.fork(owner, repo, body, current_user)
