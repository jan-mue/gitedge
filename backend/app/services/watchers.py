"""Service for watching repositories."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.entities.activity import ActivityKind, ActivityTargetType
from app.entities.watchers import Watcher
from app.schemas.social import WatchersPublic, WatcherState
from app.schemas.users import UserPublic
from app.services.repositories import ensure_repository

if TYPE_CHECKING:
    from app.clients.repositories import RepositoryStore
    from app.clients.watchers import WatcherStore
    from app.entities.users import User
    from app.services.activity import ActivityService


class WatcherService:
    """Service for watching and unwatching repositories."""

    def __init__(
        self,
        watcher_store: WatcherStore,
        repository_store: RepositoryStore,
        activity_service: ActivityService,
    ) -> None:
        """Initialize the watcher service.

        Args:
            watcher_store: Watcher store.
            repository_store: Repository store.
            activity_service: Service used to record activity.
        """
        self.watcher_store = watcher_store
        self.repository_store = repository_store
        self.activity_service = activity_service

    async def watch(self, owner: str, name: str, user: User) -> WatcherState:
        """Watch a repository.

        Args:
            owner: Owner name.
            name: Repository name.
            user: The current user.

        Returns:
            The updated watcher state.
        """
        repository = await ensure_repository(self.repository_store, owner, name)
        existing = await self.watcher_store.get_by_user_and_repo(user.id, repository.id)
        if existing is None:
            await self.watcher_store.add(Watcher(user_id=user.id, repo_id=repository.id))
            await self.activity_service.record(
                actor=user,
                repo=repository,
                kind=ActivityKind.WATCH,
                title=repository.name,
                target_type=ActivityTargetType.REPOSITORY,
            )
        return WatcherState(is_watching=True, watchers_count=await self.watcher_store.count_by_repo(repository.id))

    async def unwatch(self, owner: str, name: str, user: User) -> WatcherState:
        """Stop watching a repository.

        Args:
            owner: Owner name.
            name: Repository name.
            user: The current user.

        Returns:
            The updated watcher state.
        """
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        if repository is None:
            return WatcherState(is_watching=False, watchers_count=0)
        existing = await self.watcher_store.get_by_user_and_repo(user.id, repository.id)
        if existing is not None:
            await self.watcher_store.delete(existing)
        return WatcherState(is_watching=False, watchers_count=await self.watcher_store.count_by_repo(repository.id))

    async def state(self, owner: str, name: str, user: User) -> WatcherState:
        """Get the current user's watcher state for a repository.

        Args:
            owner: Owner name.
            name: Repository name.
            user: The current user.

        Returns:
            The watcher state.
        """
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        if repository is None:
            return WatcherState(is_watching=False, watchers_count=0)
        existing = await self.watcher_store.get_by_user_and_repo(user.id, repository.id)
        return WatcherState(
            is_watching=existing is not None,
            watchers_count=await self.watcher_store.count_by_repo(repository.id),
        )

    async def watchers(self, owner: str, name: str, offset: int = 0, limit: int = 100) -> WatchersPublic:
        """List users watching a repository.

        Args:
            owner: Owner name.
            name: Repository name.
            offset: Pagination offset.
            limit: Maximum number of users.

        Returns:
            WatchersPublic with the watchers.
        """
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        if repository is None:
            return WatchersPublic(data=[], count=0)
        watchers = await self.watcher_store.list_by_repo(repository.id, offset, limit)
        users = [UserPublic.model_validate(watcher.user) for watcher in watchers if watcher.user is not None]
        return WatchersPublic(data=users, count=len(users))
