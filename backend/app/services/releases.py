"""Service for repository releases."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.entities.activity import ActivityKind, ActivityTargetType
from app.entities.releases import Release
from app.schemas.releases import ReleaseCreate, ReleasePublic, ReleasesPublic
from app.services.repositories import ensure_repository

if TYPE_CHECKING:
    from app.clients.releases import ReleaseStore
    from app.clients.repositories import RepositoryStore
    from app.entities.users import User
    from app.services.activity import ActivityService


class ReleaseService:
    """Service for managing repository releases."""

    def __init__(
        self,
        release_store: ReleaseStore,
        repository_store: RepositoryStore,
        activity_service: ActivityService,
    ) -> None:
        """Initialize the release service.

        Args:
            release_store: Release store.
            repository_store: Repository store.
            activity_service: Service used to record activity.
        """
        self.release_store = release_store
        self.repository_store = repository_store
        self.activity_service = activity_service

    async def list_releases(self, owner: str, name: str, include_drafts: bool = False) -> ReleasesPublic:
        """List releases for a repository.

        Args:
            owner: Owner name.
            name: Repository name.
            include_drafts: Whether to include draft releases.

        Returns:
            ReleasesPublic with the releases, newest first.
        """
        repository = await self.repository_store.find_by_owner_and_name(owner, name)
        if repository is None:
            return ReleasesPublic(data=[], count=0)
        releases = await self.release_store.list_by_repo(repository.id, include_drafts)
        return ReleasesPublic(data=[self._to_public(release, owner, name) for release in releases], count=len(releases))

    async def get_release(self, owner: str, name: str, tag_name: str) -> ReleasePublic:
        """Get a single release by tag name.

        Args:
            owner: Owner name.
            name: Repository name.
            tag_name: The release tag name.

        Returns:
            The release.

        Raises:
            ReleaseNotFoundError: If the release is not found.
        """
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        release = await self.release_store.get_by_tag(repository.id, tag_name)
        return self._to_public(release, owner, name)

    async def create_release(self, owner: str, name: str, body: ReleaseCreate, current_user: User) -> ReleasePublic:
        """Create a release.

        Args:
            owner: Owner name.
            name: Repository name.
            body: Release creation data.
            current_user: The authenticated user.

        Returns:
            The created release.

        Raises:
            HTTPException: If a release for the tag already exists.
        """
        repository = await ensure_repository(self.repository_store, owner, name)
        if await self.release_store.find_by_tag(repository.id, body.tag_name) is not None:
            raise HTTPException(status_code=409, detail="A release for this tag already exists")

        release = Release(
            repo_id=repository.id,
            tag_name=body.tag_name,
            name=body.name,
            body=body.body,
            author_id=current_user.id,
            target_commitish=body.target_commitish,
            is_draft=body.is_draft,
            is_prerelease=body.is_prerelease,
            published_at=None if body.is_draft else datetime.now(UTC),
        )
        await self.release_store.add(release)
        release.author = current_user
        await self.activity_service.record(
            actor=current_user,
            repo=repository,
            kind=ActivityKind.RELEASE,
            title=body.name or body.tag_name,
            target_type=ActivityTargetType.RELEASE,
        )
        return self._to_public(release, owner, name)

    @staticmethod
    def _to_public(release: Release, owner: str, name: str) -> ReleasePublic:
        """Convert a release entity to its public representation.

        Args:
            release: The release entity (with its author loaded).
            owner: Owner name.
            name: Repository name.

        Returns:
            The public release representation.
        """
        return ReleasePublic(
            id=release.id,
            repo_owner=owner,
            repo_name=name,
            tag_name=release.tag_name,
            name=release.name,
            body=release.body,
            target_commitish=release.target_commitish,
            is_draft=release.is_draft,
            is_prerelease=release.is_prerelease,
            author_username=release.author.name if release.author is not None else None,
            published_at=release.published_at,
            created_at=release.created_at,
            updated_at=release.updated_at,
        )
