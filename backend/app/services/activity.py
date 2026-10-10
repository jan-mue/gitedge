"""Service for recording and reading activity feed events."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.entities.activity import Activity, ActivityKind, ActivityTargetType
from app.schemas.activity import ActivitiesPublic, ActivityPublic
from app.schemas.repository_activity import ActivityOverview, ActivitySeriesPoint, RepositoryActivityStatistics
from app.services.repository_activity import aggregate_contributors, aggregate_recent_commits

if TYPE_CHECKING:
    import uuid

    from app.clients.activity import ActivityStore
    from app.clients.repositories import RepositoryStore
    from app.clients.stars import StarStore
    from app.entities.repositories import Repository
    from app.entities.users import User
    from app.services.repositories import RepositoryService


class ActivityService:
    """Service for recording and reading activity events."""

    def __init__(
        self,
        activity_store: ActivityStore,
        repository_store: RepositoryStore,
        star_store: StarStore,
    ) -> None:
        """Initialize the activity service.

        Args:
            activity_store: Activity store.
            repository_store: Repository store.
            star_store: Star store used to build a personalized feed.
        """
        self.activity_store = activity_store
        self.repository_store = repository_store
        self.star_store = star_store

    async def repository_statistics(
        self, owner: str, name: str, repository_service: RepositoryService, days: int = 7
    ) -> RepositoryActivityStatistics:
        """Build all activity views from complete Git history and period events."""
        repository = await self.repository_store.find_by_owner_and_name(owner, name)
        if repository is None:
            raise HTTPException(status_code=404, detail="Repository not found")
        end = datetime.now(UTC)
        start = end - timedelta(days=days)
        history = await repository_service.activity_history(owner, name)
        events = await self.activity_store.list_in_period(repository.id, start, end)
        merged_by_number: dict[int, Activity] = {}
        for event in events:
            if event.kind == ActivityKind.PULL_REQUEST_MERGE and event.target_number is not None:
                merged_by_number.setdefault(event.target_number, event)
        merged = list(merged_by_number.values())
        proposed = [event for event in events if event.kind == ActivityKind.PULL_REQUEST_OPEN]
        closed = [event for event in events if event.kind == ActivityKind.ISSUE_CLOSE]
        opened = [event for event in events if event.kind == ActivityKind.ISSUE_OPEN]
        active_prs = {
            event.target_number
            for event in events
            if event.target_type == ActivityTargetType.PULL_REQUEST and event.target_number is not None
        }
        active_issues = {
            event.target_number
            for event in events
            if event.target_type == ActivityTargetType.ISSUE and event.target_number is not None
        }
        commits = [
            commit
            for commit in history.commits
            if not commit.is_merge and start.timestamp() <= commit.timestamp <= end.timestamp()
        ]
        default_commits = [commit for commit in commits if commit.is_default]
        daily = {
            start.date() + timedelta(days=index): ActivitySeriesPoint(date=start.date() + timedelta(days=index))
            for index in range((end.date() - start.date()).days + 1)
        }
        for commit in default_commits:
            point = daily[datetime.fromtimestamp(commit.timestamp, UTC).date()]
            point.commits += 1
            point.additions += commit.additions
            point.deletions += commit.deletions
        contributors, frequency = aggregate_contributors(history)
        return RepositoryActivityStatistics(
            start=start,
            end=end,
            default_branch=history.default_branch,
            overview=ActivityOverview(
                active_prs=len(active_prs),
                active_issues=len(active_issues),
                merged_prs=len(merged),
                proposed_prs=len({event.target_number for event in proposed}),
                closed_issues=len({event.target_number for event in closed}),
                new_issues=len({event.target_number for event in opened}),
                merge_authors=len({event.actor_id for event in merged}),
                authors=len({commit.author_email.casefold() or commit.author for commit in commits}),
                commits=len(default_commits),
                branch_commits=len(commits),
                files_changed=len({path for commit in default_commits for path in commit.files}),
                additions=sum(commit.additions for commit in default_commits),
                deletions=sum(commit.deletions for commit in default_commits),
            ),
            daily_commits=list(daily.values()),
            merged_prs=self._to_public_list(merged[:10]),
            contributors=contributors,
            code_frequency=frequency,
            recent_commits=aggregate_recent_commits(history, end),
        )

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
        repository = await self.repository_store.find_by_owner_and_name(owner, name)
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
            actor_username=activity.actor.name,
            repo_owner=repo.owner.name if repo is not None else None,
            repo_name=repo.name if repo is not None else None,
            target_type=activity.target_type,
            target_number=activity.target_number,
            created_at=activity.created_at,
        )
