"""Service for recording and reading activity feed events."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.entities.activity import Activity, ActivityKind, ActivityTargetType
from app.schemas.activity import ActivitiesPublic, ActivityPublic

if TYPE_CHECKING:
    import uuid

    from app.clients.activity import ActivityStore
    from app.clients.repositories import RepositoryStore
    from app.clients.stars import StarStore
    from app.entities.repositories import Repository
    from app.entities.users import User


class ActivityService:
    """Service for recording and reading activity events."""

    def __init__(
        self,
        activity_store: ActivityStore,
        repository_store: RepositoryStore,
        star_store: StarStore | None = None,
    ) -> None:
        """Initialize the activity service.

        Args:
            activity_store: Activity store.
            repository_store: Repository store.
            star_store: Optional star store used to build a personalized feed.
        """
        self.activity_store = activity_store
        self.repository_store = repository_store
        self.star_store = star_store

    async def record(
        self,
        *,
        actor: User,
        repo: Repository | None,
        kind: ActivityKind,
        title: str | None = None,
        target_type: ActivityTargetType | None = None,
        target_number: int | None = None,
    ) -> Activity:
        """Record an activity event.

        Args:
            actor: The user performing the action.
            repo: The repository the action relates to, if any.
            kind: The activity kind.
            title: Optional human readable title.
            target_type: Optional target type.
            target_number: Optional target number within the repository.

        Returns:
            The persisted activity entity.
        """
        activity = Activity(
            actor_id=actor.id,
            repo_id=repo.id if repo is not None else None,
            kind=kind,
            title=title,
            target_type=target_type,
            target_number=target_number,
        )
        await self.activity_store.add(activity)
        return activity

    async def repo_activity(self, owner: str, name: str, offset: int = 0, limit: int = 50) -> ActivitiesPublic:
        """List activity for a repository.

        Args:
            owner: Owner name.
            name: Repository name.
            offset: Pagination offset.
            limit: Maximum number of events.

        Returns:
            ActivitiesPublic with the repository activity, newest first.
        """
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        if repository is None:
            return ActivitiesPublic(data=[], count=0)
        activities = await self.activity_store.list_by_repo(repository.id, offset, limit)
        return ActivitiesPublic(data=self._to_public_list(activities), count=len(activities))

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
        return ActivitiesPublic(data=self._to_public_list(activities), count=len(activities))

    @staticmethod
    def _to_public_list(activities: list[Activity]) -> list[ActivityPublic]:
        """Convert activity entities to their public representation.

        Args:
            activities: The activity entities (with actor and repo loaded).

        Returns:
            The public activity representations.
        """
        return [ActivityService._to_public(activity) for activity in activities]

    @staticmethod
    def _to_public(activity: Activity) -> ActivityPublic:
        """Convert a single activity entity to its public representation."""
        repo = activity.repo
        return ActivityPublic(
            id=activity.id,
            kind=activity.kind,
            title=activity.title,
            actor_username=activity.actor.name if activity.actor is not None else None,
            repo_owner=repo.owner.name if repo is not None else None,
            repo_name=repo.name if repo is not None else None,
            target_type=activity.target_type,
            target_number=activity.target_number,
            created_at=activity.created_at,
        )
