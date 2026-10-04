"""Repository star routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies import CurrentUser, StarServiceDep
from app.schemas.repositories import RepositoriesPublic
from app.schemas.social import StargazersPublic, StarState

router = APIRouter(prefix="/repositories", tags=["stars"])
user_router = APIRouter(prefix="/users", tags=["stars"])


@router.get("/{path:path}/star")
async def get_star_state(path: str, star_service: StarServiceDep, current_user: CurrentUser) -> StarState:
    """Get the current user's star state for a repository."""
    return await star_service.state(path, current_user)


@router.put("/{path:path}/star")
async def star_repository(path: str, star_service: StarServiceDep, current_user: CurrentUser) -> StarState:
    """Star a repository."""
    return await star_service.star(path, current_user)


@router.delete("/{path:path}/star")
async def unstar_repository(path: str, star_service: StarServiceDep, current_user: CurrentUser) -> StarState:
    """Remove a star from a repository."""
    return await star_service.unstar(path, current_user)


@router.get("/{path:path}/stargazers")
async def list_stargazers(
    path: str, star_service: StarServiceDep, offset: int = 0, limit: int = 100
) -> StargazersPublic:
    """List users who starred a repository."""
    return await star_service.stargazers(path, offset, limit)


@user_router.get("/me/starred")
async def list_starred_repositories(
    star_service: StarServiceDep, current_user: CurrentUser, offset: int = 0, limit: int = 100
) -> RepositoriesPublic:
    """List repositories starred by the current user."""
    return await star_service.starred_repositories(current_user, offset, limit)
