"""Repository release and tag routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies import CurrentUser, ReleaseServiceDep, RepositoryServiceDep
from app.schemas.releases import ReleaseCreate, ReleasePublic, ReleasesPublic, ReleaseUpdate, TagsPublic

router = APIRouter(prefix="/repositories", tags=["releases"])


@router.get("/{owner}/{repo}/releases")
async def list_releases(
    owner: str, repo: str, release_service: ReleaseServiceDep, include_drafts: bool = False
) -> ReleasesPublic:
    """List releases for a repository."""
    return await release_service.list_releases(owner, repo, include_drafts)


@router.post("/{owner}/{repo}/releases", status_code=201)
async def create_release(
    owner: str, repo: str, body: ReleaseCreate, release_service: ReleaseServiceDep, current_user: CurrentUser
) -> ReleasePublic:
    """Create a release."""
    return await release_service.create_release(owner, repo, body, current_user)


@router.get("/{owner}/{repo}/releases/{tag_name}")
async def get_release(owner: str, repo: str, tag_name: str, release_service: ReleaseServiceDep) -> ReleasePublic:
    """Get a single release by tag name."""
    return await release_service.get_release(owner, repo, tag_name)


@router.patch("/{owner}/{repo}/releases/{tag_name}")
async def update_release(
    owner: str,
    repo: str,
    tag_name: str,
    body: ReleaseUpdate,
    release_service: ReleaseServiceDep,
    current_user: CurrentUser,
) -> ReleasePublic:
    """Update a release."""
    return await release_service.update_release(owner, repo, tag_name, body, current_user)


@router.get("/{owner}/{repo}/tags")
async def list_tags(owner: str, repo: str, repository_service: RepositoryServiceDep) -> TagsPublic:
    """List Git tags for a repository."""
    return await repository_service.list_tags(owner, repo)
