"""Service for starring repositories."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.entities.activity import ActivityKind, ActivityTargetType
from app.entities.stars import Star
from app.schemas.repositories import RepositoriesPublic
from app.schemas.social import StargazersPublic, StarState
from app.schemas.users import UserPublic
from app.services.repositories import ensure_repository, normalize_repo_path, to_repository_schema

if TYPE_CHECKING:
    from app.clients.repositories import RepositoryStore
    from app.clients.stars import StarStore
    from app.clients.users import UserStore
    from app.entities.users import User
    from app.services.activity import ActivityService


class StarService:
    """Service for starring and unstarring repositories."""

    def __init__(
        self,
        star_store: StarStore,
        repository_store: RepositoryStore,
        user_store: UserStore,
        activity_service: ActivityService,
    ) -> None:
        """Initialize the star service.

        Args:
            star_store: Star store.
            repository_store: Repository store.
            user_store: User store.
            activity_service: Service used to record activity.
        """
        self.star_store = star_store
        self.repository_store = repository_store
        self.user_store = user_store
        self.activity_service = activity_service

    async def star(self, path: str, user: User) -> StarState:
        """Star a repository.

        Args:
            path: Repository path.
            user: The current user.

        Returns:
            The updated star state.
        """
        repo_path = normalize_repo_path(path)
        repository = await ensure_repository(self.repository_store, repo_path, user)
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

    async def unstar(self, path: str, user: User) -> StarState:
        """Remove a star from a repository.

        Args:
            path: Repository path.
            user: The current user.

        Returns:
            The updated star state.
        """
        repo_path = normalize_repo_path(path)
        repository = await self.repository_store.get_by_path(repo_path)
        if repository is None:
            return StarState(is_starred=False, stars_count=0)
        existing = await self.star_store.get_by_user_and_repo(user.id, repository.id)
        if existing is not None:
            await self.star_store.delete(existing)
        return StarState(is_starred=False, stars_count=await self.star_store.count_by_repo(repository.id))

    async def state(self, path: str, user: User) -> StarState:
        """Get the current user's star state for a repository.

        Args:
            path: Repository path.
            user: The current user.

        Returns:
            The star state.
        """
        repo_path = normalize_repo_path(path)
        repository = await self.repository_store.get_by_path(repo_path)
        if repository is None:
            return StarState(is_starred=False, stars_count=0)
        existing = await self.star_store.get_by_user_and_repo(user.id, repository.id)
        return StarState(
            is_starred=existing is not None,
            stars_count=await self.star_store.count_by_repo(repository.id),
        )

    async def stargazers(self, path: str, offset: int = 0, limit: int = 100) -> StargazersPublic:
        """List users who starred a repository.

        Args:
            path: Repository path.
            offset: Pagination offset.
            limit: Maximum number of users.

        Returns:
            StargazersPublic with the stargazers.
        """
        repo_path = normalize_repo_path(path)
        repository = await self.repository_store.get_by_path(repo_path)
        if repository is None:
            return StargazersPublic(data=[], count=0)
        stars = await self.star_store.list_by_repo(repository.id, offset, limit)
        users: list[UserPublic] = []
        for star in stars:
            user = await self.user_store.get(star.user_id)
            if user is not None:
                users.append(UserPublic.model_validate(user))
        return StargazersPublic(data=users, count=len(users))

    async def starred_repositories(self, user: User, offset: int = 0, limit: int = 100) -> RepositoriesPublic:
        """List repositories starred by a user.

        Args:
            user: The user.
            offset: Pagination offset.
            limit: Maximum number of repositories.

        Returns:
            RepositoriesPublic with the starred repositories.
        """
        stars = await self.star_store.list_by_user(user.id, offset, limit)
        repositories = []
        for star in stars:
            repository = await self.repository_store.get(star.repo_id)
            if repository is not None:
                schema = to_repository_schema(repository)
                schema.stars_count = await self.star_store.count_by_repo(repository.id)
                schema.forks_count = await self.repository_store.count_by_fork_of(repository.id)
                repositories.append(schema)
        return RepositoriesPublic(data=repositories, count=len(repositories))
