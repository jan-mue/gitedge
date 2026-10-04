"""Repository release and tag routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies import CurrentUser, ReleaseServiceDep, RepositoryServiceDep
from app.schemas.releases import ReleaseCreate, ReleasePublic, ReleasesPublic, TagsPublic

router = APIRouter(prefix="/repositories", tags=["releases"])


@router.get("/{path:path}/releases")
async def list_releases(path: str, release_service: ReleaseServiceDep, include_drafts: bool = False) -> ReleasesPublic:
    """List releases for a repository."""
    return await release_service.list_releases(path, include_drafts)


@router.post("/{path:path}/releases", status_code=201)
async def create_release(
    path: str, body: ReleaseCreate, release_service: ReleaseServiceDep, current_user: CurrentUser
) -> ReleasePublic:
    """Create a release."""
    return await release_service.create_release(path, body, current_user)


@router.get("/{path:path}/releases/{tag_name}")
async def get_release(path: str, tag_name: str, release_service: ReleaseServiceDep) -> ReleasePublic:
    """Get a single release by tag name."""
    return await release_service.get_release(path, tag_name)


@router.get("/{path:path}/tags")
async def list_tags(path: str, repository_service: RepositoryServiceDep) -> TagsPublic:
    """List Git tags for a repository."""
    return await repository_service.list_tags(path)
