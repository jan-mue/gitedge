"""Service for recording and reading activity feed events."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.entities.activity import Activity, ActivityKind, ActivityTargetType
from app.schemas.activity import ActivitiesPublic, ActivityPublic
from app.services.repositories import normalize_repo_path

if TYPE_CHECKING:
    import uuid

    from app.clients.activity import ActivityStore
    from app.clients.repositories import RepositoryStore
    from app.clients.stars import StarStore
    from app.clients.users import UserStore
    from app.entities.repositories import Repository
    from app.entities.users import User


class ActivityService:
    """Service for recording and reading activity events."""

    def __init__(
        self,
        activity_store: ActivityStore,
        repository_store: RepositoryStore,
        user_store: UserStore,
        star_store: StarStore | None = None,
    ) -> None:
        """Initialize the activity service.

        Args:
            activity_store: Activity store.
            repository_store: Repository store.
            user_store: User store.
            star_store: Optional star store used to build a personalized feed.
        """
        self.activity_store = activity_store
        self.repository_store = repository_store
        self.user_store = user_store
        self.star_store = star_store

    async def record(
        self,
        *,
        actor: User | None,
        repo: Repository | None,
        kind: ActivityKind,
        title: str | None = None,
        target_type: ActivityTargetType | None = None,
        target_number: int | None = None,
    ) -> Activity:
        """Record an activity event.

        Args:
            actor: The user performing the action, if any.
            repo: The repository the action relates to, if any.
            kind: The activity kind.
            title: Optional human readable title.
            target_type: Optional target type.
            target_number: Optional target number within the repository.

        Returns:
            The persisted activity entity.
        """
        activity = Activity(
            actor_id=actor.id if actor is not None else None,
            actor_email=actor.email if actor is not None else None,
            repo_id=repo.id if repo is not None else None,
            kind=kind,
            title=title,
            target_type=target_type,
            target_number=target_number,
        )
        await self.activity_store.add(activity)
        return activity

    async def repo_activity(self, path: str, offset: int = 0, limit: int = 50) -> ActivitiesPublic:
        """List activity for a repository.

        Args:
            path: Repository path.
            offset: Pagination offset.
            limit: Maximum number of events.

        Returns:
            ActivitiesPublic with the repository activity, newest first.
        """
        repo_path = normalize_repo_path(path)
        repository = await self.repository_store.get_by_path(repo_path)
        if repository is None:
            return ActivitiesPublic(data=[], count=0)
        activities = await self.activity_store.list_by_repo(repository.id, offset, limit)
        return ActivitiesPublic(data=await self._to_public_list(activities), count=len(activities))

    async def feed(self, user: User, offset: int = 0, limit: int = 50) -> ActivitiesPublic:
        """Build a personalized feed for a user.

        The feed combines activity from repositories the user owns or has
        starred. If the user has no such repositories, the globally most
        recent activity is returned instead.

        Args:
            user: The current user.
            offset: Pagination offset.
            limit: Maximum number of events.

        Returns:
            ActivitiesPublic with the feed events, newest first.
        """
        repo_ids: set[uuid.UUID] = set()
        owned = await self.repository_store.get_by_owner(user.id, 0, 1000)
        repo_ids.update(repository.id for repository in owned)
        if self.star_store is not None:
            stars = await self.star_store.list_by_user(user.id, 0, 1000)
            repo_ids.update(star.repo_id for star in stars)

        activities = await self.activity_store.list_by_repos(list(repo_ids), offset, limit) if repo_ids else []
        if not activities:
            activities = await self.activity_store.list_recent(offset, limit)
        return ActivitiesPublic(data=await self._to_public_list(activities), count=len(activities))

    async def _to_public_list(self, activities: list[Activity]) -> list[ActivityPublic]:
        """Convert activity entities to their public representation.

        Args:
            activities: The activity entities.

        Returns:
            The public activity representations.
        """
        repo_paths: dict[uuid.UUID, str] = {}
        usernames: dict[uuid.UUID, str] = {}
        for activity in activities:
            if activity.repo_id is not None and activity.repo_id not in repo_paths:
                repository = await self.repository_store.get(activity.repo_id)
                if repository is not None:
                    repo_paths[activity.repo_id] = repository.path
            if activity.actor_id is not None and activity.actor_id not in usernames:
                actor = await self.user_store.get(activity.actor_id)
                if actor is not None and actor.username:
                    usernames[activity.actor_id] = actor.username

        return [self._to_public(activity, repo_paths, usernames) for activity in activities]

    @staticmethod
    def _to_public(
        activity: Activity,
        repo_paths: dict[uuid.UUID, str],
        usernames: dict[uuid.UUID, str],
    ) -> ActivityPublic:
        """Convert a single activity entity to its public representation."""
        return ActivityPublic(
            id=activity.id,
            kind=activity.kind,
            title=activity.title,
            actor_email=activity.actor_email,
            actor_username=usernames.get(activity.actor_id) if activity.actor_id else None,
            repo_path=repo_paths.get(activity.repo_id) if activity.repo_id else None,
            target_type=activity.target_type,
            target_number=activity.target_number,
            created_at=activity.created_at,
        )
