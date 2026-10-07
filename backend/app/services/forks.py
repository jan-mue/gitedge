"""Service for forking repositories."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.entities.activity import ActivityKind, ActivityTargetType
from app.entities.repositories import Repository
from app.schemas.social import ForkCreate, ForkPublic, ForksPublic

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

    async def fork(self, owner: str, name: str, body: ForkCreate, current_user: User) -> ForkPublic:
        """Fork a repository.

        Args:
            owner: Source repository owner name.
            name: Source repository name.
            body: Fork options.
            current_user: The authenticated user.

        Returns:
            The created fork.

        Raises:
            HTTPException: If the source is not found or the target already exists.
        """
        source = await self.repository_store.get_by_owner_and_name(owner, name)

        dest_owner = body.owner or current_user.name
        dest_name = body.name or source.name

        if dest_owner.lower() == source.owner.name.lower():
            raise HTTPException(status_code=400, detail="Cannot fork a repository into the same owner")

        owner_id, _ = await self.repository_store.resolve_owner(dest_owner)

        if await self.repository_store.find_by_owner_and_name(dest_owner, dest_name) is not None:
            raise HTTPException(status_code=409, detail="A repository with that name already exists")

        fork = Repository(
            name=dest_name,
            owner_id=owner_id,
            description=body.description or source.description,
            default_branch=source.default_branch,
            fork_of_id=source.id,
        )
        await self.repository_store.add(fork)

        await self.repository_service.create_repository(dest_owner, dest_name)

        await self.activity_service.record(
            actor=current_user,
            repo=source,
            kind=ActivityKind.FORK,
            title=source.name,
            target_type=ActivityTargetType.REPOSITORY,
        )

        return await self._to_public(fork)

    async def list_forks(self, owner: str, name: str, offset: int = 0, limit: int = 100) -> ForksPublic:
        """List forks of a repository.

        Args:
            owner: Owner name.
            name: Repository name.
            offset: Pagination offset.
            limit: Maximum number of forks.

        Returns:
            ForksPublic with the forks.
        """
        source = await self.repository_store.find_by_owner_and_name(owner, name)
        if source is None:
            return ForksPublic(data=[], count=0)
        forks = await self.repository_store.list_by_fork_of(source.id, offset, limit)
        return ForksPublic(data=[await self._to_public(fork) for fork in forks], count=len(forks))

    async def _to_public(self, fork: Repository) -> ForkPublic:
        """Convert a fork entity to its public representation.

        Args:
            fork: The fork repository entity (with its owner loaded).

        Returns:
            The public fork representation.
        """
        stars_count = await self.star_store.count_by_repo(fork.id) if self.star_store is not None else 0
        forks_count = await self.repository_store.count_by_fork_of(fork.id)
        return ForkPublic(
            id=fork.id,
            name=fork.name,
            owner=fork.owner.name,
            description=fork.description,
            stars_count=stars_count,
            forks_count=forks_count,
            created_at=fork.created_at,
        )
