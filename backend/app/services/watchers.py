"""Service for watching repositories."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.entities.watchers import Watcher
from app.schemas.social import WatchersPublic, WatcherState
from app.schemas.users import UserPublic
from app.services.repositories import ensure_repository, normalize_repo_path

if TYPE_CHECKING:
    from app.clients.repositories import RepositoryStore
    from app.clients.users import UserStore
    from app.clients.watchers import WatcherStore
    from app.entities.users import User
    from app.services.activity import ActivityService


class WatcherService:
    """Service for watching and unwatching repositories."""

    def __init__(
        self,
        watcher_store: WatcherStore,
        repository_store: RepositoryStore,
        user_store: UserStore,
        activity_service: ActivityService,
    ) -> None:
        """Initialize the watcher service.

        Args:
            watcher_store: Watcher store.
            repository_store: Repository store.
            user_store: User store.
            activity_service: Service used to record activity.
        """
        self.watcher_store = watcher_store
        self.repository_store = repository_store
        self.user_store = user_store
        self.activity_service = activity_service

    async def watch(self, path: str, user: User) -> WatcherState:
        """Watch a repository.

        Args:
            path: Repository path.
            user: The current user.

        Returns:
            The updated watcher state.
        """
        repo_path = normalize_repo_path(path)
        repository = await ensure_repository(self.repository_store, repo_path, user)
        existing = await self.watcher_store.get_by_user_and_repo(user.id, repository.id)
        if existing is None:
            await self.watcher_store.add(Watcher(user_id=user.id, repo_id=repository.id))
            await self.activity_service.record(
                actor=user, repo=repository, kind="watch", title=repository.name, target_type="repository"
            )
        return WatcherState(is_watching=True, watchers_count=await self.watcher_store.count_by_repo(repository.id))

    async def unwatch(self, path: str, user: User) -> WatcherState:
        """Stop watching a repository.

        Args:
            path: Repository path.
            user: The current user.

        Returns:
            The updated watcher state.
        """
        repo_path = normalize_repo_path(path)
        repository = await self.repository_store.get_by_path(repo_path)
        if repository is None:
            return WatcherState(is_watching=False, watchers_count=0)
        existing = await self.watcher_store.get_by_user_and_repo(user.id, repository.id)
        if existing is not None:
            await self.watcher_store.delete(existing)
        return WatcherState(is_watching=False, watchers_count=await self.watcher_store.count_by_repo(repository.id))

    async def state(self, path: str, user: User) -> WatcherState:
        """Get the current user's watcher state for a repository.

        Args:
            path: Repository path.
            user: The current user.

        Returns:
            The watcher state.
        """
        repo_path = normalize_repo_path(path)
        repository = await self.repository_store.get_by_path(repo_path)
        if repository is None:
            return WatcherState(is_watching=False, watchers_count=0)
        existing = await self.watcher_store.get_by_user_and_repo(user.id, repository.id)
        return WatcherState(
            is_watching=existing is not None,
            watchers_count=await self.watcher_store.count_by_repo(repository.id),
        )

    async def watchers(self, path: str, offset: int = 0, limit: int = 100) -> WatchersPublic:
        """List users watching a repository.

        Args:
            path: Repository path.
            offset: Pagination offset.
            limit: Maximum number of users.

        Returns:
            WatchersPublic with the watchers.
        """
        repo_path = normalize_repo_path(path)
        repository = await self.repository_store.get_by_path(repo_path)
        if repository is None:
            return WatchersPublic(data=[], count=0)
        watchers = await self.watcher_store.list_by_repo(repository.id, offset, limit)
        users: list[UserPublic] = []
        for watcher in watchers:
            user = await self.user_store.get(watcher.user_id)
            if user is not None:
                users.append(UserPublic.model_validate(user))
        return WatchersPublic(data=users, count=len(users))
