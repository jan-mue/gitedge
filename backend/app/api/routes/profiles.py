"""User profile routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.dependencies import RepositoryServiceDep, StarServiceDep, UserStoreDep
from app.schemas.repositories import RepositoriesPublic
from app.schemas.users import UserPublic

router = APIRouter(prefix="/users", tags=["profiles"])


@router.get("/by-username/{username}")
async def read_user_by_username(username: str, user_store: UserStoreDep) -> UserPublic:
    """Get a user by username."""
    user = await user_store.get_by_username(username)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserPublic.model_validate(user)


@router.get("/by-username/{username}/repositories")
async def list_user_repositories(
    username: str, user_store: UserStoreDep, repository_service: RepositoryServiceDep
) -> RepositoriesPublic:
    """List repositories owned by a user."""
    user = await user_store.get_by_username(username)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return await repository_service.get_user_repositories(user)


@router.get("/by-username/{username}/starred")
async def list_user_starred_repositories(
    username: str, user_store: UserStoreDep, star_service: StarServiceDep
) -> RepositoriesPublic:
    """List repositories starred by a user."""
    user = await user_store.get_by_username(username)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return await star_service.starred_repositories(user)
