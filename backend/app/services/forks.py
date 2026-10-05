"""Service for forking repositories."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.entities.activity import ActivityKind, ActivityTargetType
from app.entities.repositories import Repository
from app.schemas.social import ForkCreate, ForkPublic, ForksPublic
from app.services.repositories import (
    normalize_repo_path,
    repository_name_from_path,
    repository_owner_from_path,
)

if TYPE_CHECKING:
    from app.clients.repositories import RepositoryStore
    from app.clients.stars import StarStore
    from app.entities.users import User
    from app.services.activity import ActivityService
    from app.services.repositories import RepositoryService


class ForkService:
    """Service for forking and listing repository forks."""

    def __init__(
        self,
        repository_store: RepositoryStore,
        repository_service: RepositoryService,
        activity_service: ActivityService,
        star_store: StarStore | None = None,
    ) -> None:
        """Initialize the fork service.

        Args:
            repository_store: Repository store.
            repository_service: Repository service used to create the Git repo.
            activity_service: Service used to record activity.
            star_store: Optional star store used to compute star counts.
        """
        self.repository_store = repository_store
        self.repository_service = repository_service
        self.activity_service = activity_service
        self.star_store = star_store

    async def fork(self, path: str, body: ForkCreate, current_user: User) -> ForkPublic:
        """Fork a repository.

        Args:
            path: Source repository path.
            body: Fork options.
            current_user: The authenticated user.

        Returns:
            The created fork.

        Raises:
            HTTPException: If the source is not found or the target already exists.
        """
        source_path = normalize_repo_path(path)
        source = await self.repository_store.get_by_path(source_path)
        if source is None:
            # Repositories pushed directly via Git have no metadata row yet.
            # Ensure the Git repository exists before registering it.
            await self.repository_service.get_repository(source_path)
            source = Repository(name=repository_name_from_path(source_path), path=source_path)
            await self.repository_store.add(source)

        owner = body.owner or current_user.username or current_user.email.split("@")[0]
        name = body.name or source.name
        dest_path = normalize_repo_path(f"{owner}/{name}")
        if await self.repository_store.get_by_path(dest_path) is not None:
            raise HTTPException(status_code=409, detail="A repository with that name already exists")

        fork = Repository(
            name=name,
            path=dest_path,
            owner_id=current_user.id,
            description=body.description or source.description,
            default_branch=source.default_branch,
            fork_of_id=source.id,
        )
        await self.repository_store.add(fork)

        await self.repository_service.create_repository(owner, name)

        await self.activity_service.record(
            actor=current_user,
            repo=source,
            kind=ActivityKind.FORK,
            title=source.name,
            target_type=ActivityTargetType.REPOSITORY,
        )

        return await self._to_public(fork)

    async def list_forks(self, path: str, offset: int = 0, limit: int = 100) -> ForksPublic:
        """List forks of a repository.

        Args:
            path: Repository path.
            offset: Pagination offset.
            limit: Maximum number of forks.

        Returns:
            ForksPublic with the forks.
        """
        source_path = normalize_repo_path(path)
        source = await self.repository_store.get_by_path(source_path)
        if source is None:
            return ForksPublic(data=[], count=0)
        forks = await self.repository_store.list_by_fork_of(source.id, offset, limit)
        return ForksPublic(data=[await self._to_public(fork) for fork in forks], count=len(forks))

    async def _to_public(self, fork: Repository) -> ForkPublic:
        """Convert a fork entity to its public representation.

        Args:
            fork: The fork repository entity.

        Returns:
            The public fork representation.
        """
        stars_count = await self.star_store.count_by_repo(fork.id) if self.star_store is not None else 0
        forks_count = await self.repository_store.count_by_fork_of(fork.id)
        return ForkPublic(
            id=fork.id,
            path=fork.path,
            name=fork.name,
            owner=repository_owner_from_path(fork.path),
            description=fork.description,
            stars_count=stars_count,
            forks_count=forks_count,
            created_at=fork.created_at,
        )
