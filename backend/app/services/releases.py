"""Service for repository releases."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.entities.activity import ActivityKind, ActivityTargetType
from app.entities.releases import Release
from app.schemas.releases import ReleaseCreate, ReleasePublic, ReleasesPublic
from app.services.repositories import ensure_repository, normalize_repo_path

if TYPE_CHECKING:
    import uuid

    from app.clients.releases import ReleaseStore
    from app.clients.repositories import RepositoryStore
    from app.clients.users import UserStore
    from app.entities.users import User
    from app.services.activity import ActivityService


class ReleaseService:
    """Service for managing repository releases."""

    def __init__(
        self,
        release_store: ReleaseStore,
        repository_store: RepositoryStore,
        user_store: UserStore,
        activity_service: ActivityService,
    ) -> None:
        """Initialize the release service.

        Args:
            release_store: Release store.
            repository_store: Repository store.
            user_store: User store.
            activity_service: Service used to record activity.
        """
        self.release_store = release_store
        self.repository_store = repository_store
        self.user_store = user_store
        self.activity_service = activity_service

    async def list_releases(self, path: str, include_drafts: bool = False) -> ReleasesPublic:
        """List releases for a repository.

        Args:
            path: Repository path.
            include_drafts: Whether to include draft releases.

        Returns:
            ReleasesPublic with the releases, newest first.
        """
        repo_path = normalize_repo_path(path)
        repository = await self.repository_store.get_by_path(repo_path)
        if repository is None:
            return ReleasesPublic(data=[], count=0)
        releases = await self.release_store.list_by_repo(repository.id, include_drafts)
        return ReleasesPublic(data=await self._to_public_list(releases, repo_path), count=len(releases))

    async def get_release(self, path: str, tag_name: str) -> ReleasePublic:
        """Get a single release by tag name.

        Args:
            path: Repository path.
            tag_name: The release tag name.

        Returns:
            The release.

        Raises:
            HTTPException: If the release is not found.
        """
        repo_path = normalize_repo_path(path)
        repository = await self.repository_store.get_by_path(repo_path)
        if repository is None:
            raise HTTPException(status_code=404, detail="Release not found")
        release = await self.release_store.get_by_tag(repository.id, tag_name)
        if release is None:
            raise HTTPException(status_code=404, detail="Release not found")
        return await self._to_public(release, repo_path)

    async def create_release(self, path: str, body: ReleaseCreate, current_user: User) -> ReleasePublic:
        """Create a release.

        Args:
            path: Repository path.
            body: Release creation data.
            current_user: The authenticated user.

        Returns:
            The created release.

        Raises:
            HTTPException: If a release for the tag already exists.
        """
        repo_path = normalize_repo_path(path)
        repository = await ensure_repository(self.repository_store, repo_path, current_user)
        if await self.release_store.get_by_tag(repository.id, body.tag_name) is not None:
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
        await self.activity_service.record(
            actor=current_user,
            repo=repository,
            kind=ActivityKind.RELEASE,
            title=body.name or body.tag_name,
            target_type=ActivityTargetType.RELEASE,
        )
        return await self._to_public(release, repo_path)

    async def _to_public_list(self, releases: list[Release], repo_path: str) -> list[ReleasePublic]:
        """Convert release entities to their public representation.

        Args:
            releases: The release entities.
            repo_path: The repository path.

        Returns:
            The public release representations.
        """
        usernames: dict[uuid.UUID, str] = {}
        for release in releases:
            if release.author_id is not None and release.author_id not in usernames:
                user = await self.user_store.get(release.author_id)
                if user is not None and user.username:
                    usernames[release.author_id] = user.username
        return [self._to_public_sync(release, repo_path, usernames) for release in releases]

    async def _to_public(self, release: Release, repo_path: str) -> ReleasePublic:
        """Convert a single release entity to its public representation.

        Args:
            release: The release entity.
            repo_path: The repository path.

        Returns:
            The public release representation.
        """
        username = None
        if release.author_id is not None:
            user = await self.user_store.get(release.author_id)
            if user is not None:
                username = user.username
        usernames: dict[uuid.UUID, str] = {}
        if release.author_id is not None and username is not None:
            usernames[release.author_id] = username
        return self._to_public_sync(release, repo_path, usernames)

    @staticmethod
    def _to_public_sync(release: Release, repo_path: str, usernames: dict[uuid.UUID, str]) -> ReleasePublic:
        """Build a public release representation from an entity and username map."""
        return ReleasePublic(
            id=release.id,
            repo_path=repo_path,
            tag_name=release.tag_name,
            name=release.name,
            body=release.body,
            target_commitish=release.target_commitish,
            is_draft=release.is_draft,
            is_prerelease=release.is_prerelease,
            author_username=usernames.get(release.author_id) if release.author_id else None,
            published_at=release.published_at,
            created_at=release.created_at,
            updated_at=release.updated_at,
        )
