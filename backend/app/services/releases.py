"""Service for repository releases."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.entities.activity import ActivityKind, ActivityTargetType
from app.entities.releases import Release
from app.exceptions import ConflictError, ReleaseNotFoundError
from app.schemas.releases import ReleaseCreate, ReleasePublic, ReleasesPublic, ReleaseUpdate
from app.services.repositories import ensure_repository

if TYPE_CHECKING:
    from app.clients.releases import ReleaseStore
    from app.clients.repositories import RepositoryStore
    from app.entities.users import User
    from app.services.activity import ActivityService
    from app.services.authorization import AuthorizationService


class ReleaseService:
    """Service for managing repository releases."""

    def __init__(
        self,
        release_store: ReleaseStore,
        repository_store: RepositoryStore,
        activity_service: ActivityService,
        authorization: AuthorizationService,
    ) -> None:
        """Initialize the release service.

        Args:
            authorization: Authorization service for scoped role checks.
            release_store: Release store.
            repository_store: Repository store.
            activity_service: Service used to record activity.
        """
        self.authorization = authorization
        self.release_store = release_store
        self.repository_store = repository_store
        self.activity_service = activity_service

    async def list_releases(
        self, owner: str, name: str, include_drafts: bool = False, user: User | None = None
    ) -> ReleasesPublic:
        """List releases for a repository.

        Args:
            user: Authenticated viewer, or anonymous for public reads.
            owner: Owner name.
            name: Repository name.
            include_drafts: Whether to include draft releases.

        Returns:
            ReleasesPublic with the releases, newest first.
        """
        repository = await self.repository_store.find_by_owner_and_name(owner, name, include_releases=True)
        if repository is None:
            return ReleasesPublic(data=[], count=0)
        if include_drafts:
            await self.authorization.require(repository, user, "releases:drafts")
        releases = [release for release in repository.releases if include_drafts or not release.is_draft]
        return ReleasesPublic(data=[self._to_public(release, owner, name) for release in releases], count=len(releases))

    async def get_release(self, owner: str, name: str, tag_name: str, user: User | None = None) -> ReleasePublic:
        """Get a single release by tag name.

        Args:
            user: Authenticated viewer, or anonymous for public reads.
            owner: Owner name.
            name: Repository name.
            tag_name: The release tag name.

        Returns:
            The release.

        Raises:
            ReleaseNotFoundError: If the release is not found.
        """
        release = await self._find_release(owner, name, tag_name)
        if release.is_draft:
            repository = await self.repository_store.get_by_owner_and_name(owner, name)
            await self.authorization.require(repository, user, "releases:drafts")
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
            ApplicationError: If a release for the tag already exists.
        """
        repository = await ensure_repository(self.repository_store, owner, name, include_releases=True)
        if any(release.tag_name == body.tag_name for release in repository.releases):
            raise ConflictError(detail="A release for this tag already exists")

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
        if not release.is_draft:
            await self.activity_service.record(
                actor=current_user,
                repo=repository,
                kind=ActivityKind.RELEASE,
                title=body.name or body.tag_name,
                target_type=ActivityTargetType.RELEASE,
                text=release.body or "",
            )
        return self._to_public(release, owner, name)

    async def update_release(
        self, owner: str, name: str, tag_name: str, body: ReleaseUpdate, current_user: User
    ) -> ReleasePublic:
        """Update a release.

        Args:
            owner: Owner name.
            name: Repository name.
            tag_name: The release tag name.
            body: Fields to update.
            current_user: The authenticated user.

        Returns:
            The updated release.

        Raises:
            ReleaseNotFoundError: If the release is not found.
            ApplicationError: If the user is not allowed to edit the release.
        """
        release = await self._find_release(owner, name, tag_name)
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        await self.authorization.require(repository, current_user, "releases:write")

        was_draft = release.is_draft
        if body.name is not None:
            release.name = body.name
        if body.body is not None:
            release.body = body.body
        if body.is_prerelease is not None:
            release.is_prerelease = body.is_prerelease
        if body.is_draft is not None:
            release.is_draft = body.is_draft
            if not body.is_draft and release.published_at is None:
                release.published_at = datetime.now(UTC)

        release.updated_at = datetime.now(UTC)
        await self.release_store.update(release)
        if was_draft and not release.is_draft:
            repository = await self.repository_store.get_by_owner_and_name(owner, name)
            await self.activity_service.record(
                actor=current_user,
                repo=repository,
                kind=ActivityKind.RELEASE,
                title=release.name or release.tag_name,
                target_type=ActivityTargetType.RELEASE,
                text=release.body or "",
            )
        return self._to_public(release, owner, name)

    async def _find_release(self, owner: str, name: str, tag_name: str) -> Release:
        """Find a release by repository and tag name.

        Args:
            owner: Owner name.
            name: Repository name.
            tag_name: The release tag name.

        Returns:
            The release entity (with its author loaded).

        Raises:
            ReleaseNotFoundError: If the repository or release is not found.
        """
        repository = await self.repository_store.get_by_owner_and_name(owner, name, include_releases=True)
        release = next((release for release in repository.releases if release.tag_name == tag_name), None)
        if release is None:
            raise ReleaseNotFoundError
        return release

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
            author_username=release.author.name,
            published_at=release.published_at,
            created_at=release.created_at,
            updated_at=release.updated_at,
        )
