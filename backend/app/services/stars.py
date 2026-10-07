"""Service for starring repositories."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.entities.activity import ActivityKind, ActivityTargetType
from app.entities.stars import Star
from app.schemas.repositories import RepositoriesPublic, Repository
from app.schemas.social import StargazersPublic, StarState
from app.schemas.users import UserPublic
from app.services.repositories import ensure_repository

if TYPE_CHECKING:
    import uuid

    from app.clients.repositories import RepositoryStore
    from app.clients.stars import StarStore
    from app.entities.users import User
    from app.services.activity import ActivityService


class StarService:
    """Service for starring and unstarring repositories."""

    def __init__(
        self,
        star_store: StarStore,
        repository_store: RepositoryStore,
        activity_service: ActivityService,
    ) -> None:
        """Initialize the star service.

        Args:
            star_store: Star store.
            repository_store: Repository store.
            activity_service: Service used to record activity.
        """
        self.star_store = star_store
        self.repository_store = repository_store
        self.activity_service = activity_service

    async def star(self, owner: str, name: str, user: User) -> StarState:
        """Star a repository.

        Args:
            owner: Owner name.
            name: Repository name.
            user: The current user.

        Returns:
            The updated star state.
        """
        repository = await ensure_repository(self.repository_store, owner, name)
        existing = await self.star_store.get_by_user_and_repo(user.id, repository.id)
        if existing is None:
            await self.star_store.add(Star(user_id=user.id, repo_id=repository.id))
            await self.activity_service.record(
                actor=user,
                repo=repository,
                kind=ActivityKind.STAR,
                title=repository.name,
                target_type=ActivityTargetType.REPOSITORY,
            )
        return StarState(is_starred=True, stars_count=await self.star_store.count_by_repo(repository.id))

    async def unstar(self, owner: str, name: str, user: User) -> StarState:
        """Remove a star from a repository.

        Args:
            owner: Owner name.
            name: Repository name.
            user: The current user.

        Returns:
            The updated star state.
        """
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        if repository is None:
            return StarState(is_starred=False, stars_count=0)
        existing = await self.star_store.get_by_user_and_repo(user.id, repository.id)
        if existing is not None:
            await self.star_store.delete(existing)
        return StarState(is_starred=False, stars_count=await self.star_store.count_by_repo(repository.id))

    async def state(self, owner: str, name: str, user: User) -> StarState:
        """Get the current user's star state for a repository.

        Args:
            owner: Owner name.
            name: Repository name.
            user: The current user.

        Returns:
            The star state.
        """
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        if repository is None:
            return StarState(is_starred=False, stars_count=0)
        existing = await self.star_store.get_by_user_and_repo(user.id, repository.id)
        return StarState(
            is_starred=existing is not None,
            stars_count=await self.star_store.count_by_repo(repository.id),
        )

    async def stargazers(self, owner: str, name: str, offset: int = 0, limit: int = 100) -> StargazersPublic:
        """List users who starred a repository.

        Args:
            owner: Owner name.
            name: Repository name.
            offset: Pagination offset.
            limit: Maximum number of users.

        Returns:
            StargazersPublic with the stargazers.
        """
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        if repository is None:
            return StargazersPublic(data=[], count=0)
        stars = await self.star_store.list_by_repo(repository.id, offset, limit)
        users = [UserPublic.model_validate(star.user) for star in stars if star.user is not None]
        return StargazersPublic(data=users, count=len(users))

    async def starred_repositories(self, user_id: uuid.UUID, offset: int = 0, limit: int = 100) -> RepositoriesPublic:
        """List repositories starred by a user.

        Args:
            user_id: The user id.
            offset: Pagination offset.
            limit: Maximum number of repositories.

        Returns:
            RepositoriesPublic with the starred repositories.
        """
        stars = await self.star_store.list_by_user(user_id, offset, limit)
        repositories: list[Repository] = []
        for star in stars:
            repository = await self.repository_store.get(star.repo_id)
            if repository is None:
                continue
            schema = Repository(
                name=repository.name,
                owner=repository.owner.name,
                description=repository.description,
                default_branch=repository.default_branch,
                is_private=repository.is_private,
                created_at=repository.created_at,
                updated_at=repository.updated_at,
            )
            schema.stars_count = await self.star_store.count_by_repo(repository.id)
            schema.forks_count = await self.repository_store.count_by_fork_of(repository.id)
            repositories.append(schema)
        return RepositoriesPublic(data=repositories, count=len(repositories))
