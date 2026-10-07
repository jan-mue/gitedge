"""In-memory fakes for clients used in unit tests."""

from __future__ import annotations

import fnmatch
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import TYPE_CHECKING

from sqlalchemy.schema import ColumnDefault

from app.clients.activity import ActivityStore
from app.clients.blob_storage import BlobStorageClient
from app.clients.comments import CommentStore
from app.clients.database import CrudStore
from app.clients.email import EmailClient
from app.clients.issues import IssueStore
from app.clients.organizations import OrganizationStore
from app.clients.pull_requests import PullRequestStore
from app.clients.redis import AbstractRedisClient
from app.clients.releases import ReleaseStore
from app.clients.repositories import RepositoryStore
from app.clients.stars import StarStore
from app.clients.users import UserStore
from app.clients.watchers import WatcherStore
from app.config import settings
from app.entities.activity import Activity
from app.entities.base import Base
from app.entities.comments import Comment
from app.entities.issues import Issue, IssueState
from app.entities.organizations import Organization
from app.entities.principals import Principal, PrincipalType
from app.entities.pull_requests import PullRequest
from app.entities.releases import Release
from app.entities.repositories import Repository
from app.entities.stars import Star
from app.entities.users import User
from app.entities.watchers import Watcher
from app.utils.security import get_password_hash

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger(__name__)


class FakeEmailClient(EmailClient):
    def send_email(self, email_to: str, subject: str = "", html_content: str = "") -> None:
        logger.info("Sending email to %s with subject %s and content %s", email_to, subject, html_content)


class FakeBlobStorageClient(BlobStorageClient):
    """In-memory blob storage client."""

    def __init__(self) -> None:
        """Initialize the client."""
        self.objects: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes) -> None:
        """Store binary data at the given key."""
        self.objects[key] = data

    async def get(self, key: str) -> bytes | None:
        """Retrieve binary data for the given key."""
        return self.objects.get(key)

    async def delete(self, key: str) -> None:
        """Delete data at the given key."""
        self.objects.pop(key, None)

    async def list_keys(self, prefix: str) -> list[str]:
        """List all keys with the given prefix."""
        return [key for key in self.objects if key.startswith(prefix)]


class FakeRedisClient(AbstractRedisClient):
    """In-memory Redis client."""

    def __init__(self) -> None:
        """Initialize the client."""
        self.values: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        """Get a value from Redis."""
        return self.values.get(key)

    async def set(self, key: str, value: str | bytes) -> None:
        """Set a value in Redis."""
        self.values[key] = value.encode() if isinstance(value, str) else value

    async def delete(self, key: str) -> None:
        """Delete a key from Redis."""
        self.values.pop(key, None)

    async def scan_keys(self, pattern: str) -> list[str]:
        """Scan for keys matching a pattern."""
        return fnmatch.filter(self.values, pattern)


class FakeCrudStore[T: Base](CrudStore[T]):
    """In-memory CRUD store."""

    def __init__(self) -> None:
        """Initialize the store."""
        self.items: dict[uuid.UUID, T] = {}

    def persist(self, obj: T) -> None:
        """Insert an entity synchronously, assigning an id and timestamp."""
        for column in type(obj).__mapper__.columns:
            default = column.default
            if isinstance(default, ColumnDefault) and default.is_scalar and getattr(obj, column.key, None) is None:
                setattr(obj, column.key, default.arg)
        if obj.id is None:
            obj.id = uuid.uuid4()
        if obj.created_at is None:
            obj.created_at = datetime.now(UTC)
        self.items[obj.id] = obj

    async def get(self, primary_key: uuid.UUID) -> T | None:
        """Get an entity by its primary key."""
        return self.items.get(primary_key)

    async def get_all(self, offset: int = 0, limit: int = 100) -> list[T]:
        """Get all entities with pagination."""
        return list(self.items.values())[offset : offset + limit]

    async def count(self) -> int:
        """Count all entities."""
        return len(self.items)

    async def add(self, obj: T) -> None:
        """Add a new entity."""
        self.persist(obj)

    async def update(self, obj: T, new_data: dict[str, Any] | None = None) -> None:
        """Update an existing entity."""
        if new_data:
            for key, value in new_data.items():
                setattr(obj, key, value)
        self.items[obj.id] = obj

    async def delete(self, obj: T) -> None:
        """Delete an entity."""
        self.items.pop(obj.id, None)

    async def refresh(self, obj: T) -> None:
        """Refresh an entity (no-op for in-memory storage)."""


class FakeUserStore(FakeCrudStore[User], UserStore):
    """In-memory user store."""

    async def get_by_email(self, email: str) -> User | None:
        """Get a user by their email address."""
        return next((user for user in self.items.values() if user.email == email), None)

    async def get_by_name(self, name: str) -> User | None:
        """Get a user by their name (case-insensitive)."""
        return next((user for user in self.items.values() if user.lower_name == name.lower()), None)


class FakeOrganizationStore(FakeCrudStore[Organization], OrganizationStore):
    """In-memory organization store."""

    async def get_by_name(self, name: str) -> Organization | None:
        """Get an organization by its name (case-insensitive)."""
        return next(
            (organization for organization in self.items.values() if organization.lower_name == name.lower()), None
        )


class FakeRepositoryStore(FakeCrudStore[Repository], RepositoryStore):
    """In-memory repository store."""

    def __init__(self, users: FakeUserStore | None = None, organizations: FakeOrganizationStore | None = None) -> None:
        """Initialize the store.

        Args:
            users: Optional user store used to resolve owners.
            organizations: Optional organization store used to resolve owners.
        """
        super().__init__()
        self.users = users
        self.organizations = organizations

    def _owner(self, repository: Repository) -> Principal | None:
        """Resolve a repository's owner principal."""
        if self.organizations is not None:
            organization = self.organizations.items.get(repository.owner_id)
            if organization is not None:
                return organization
        if self.users is not None:
            return self.users.items.get(repository.owner_id)
        return None

    def _hydrate(self, repository: Repository) -> Repository:
        """Populate a repository's relationships from the other fake stores."""
        owner = self._owner(repository)
        if owner is not None:
            repository.owner = owner
        if repository.fork_of_id is not None:
            fork_of = self.items.get(repository.fork_of_id)
            if fork_of is not None:
                repository.fork_of = fork_of
        return repository

    async def get(self, primary_key: uuid.UUID) -> Repository | None:
        """Get a repository by its primary key."""
        repository = self.items.get(primary_key)
        return self._hydrate(repository) if repository is not None else None

    async def get_all(self, offset: int = 0, limit: int = 100) -> list[Repository]:
        """Get all repositories with pagination."""
        return [self._hydrate(repository) for repository in list(self.items.values())[offset : offset + limit]]

    async def add(self, obj: Repository) -> None:
        """Add a repository and populate its relationships."""
        self.persist(obj)
        self._hydrate(obj)

    async def get_by_owner_and_name(self, owner: str, name: str) -> Repository | None:
        """Get a repository by its owner name and name."""
        for repository in self.items.values():
            principal = self._owner(repository)
            if repository.name == name and principal is not None and principal.name.lower() == owner.lower():
                return self._hydrate(repository)
        return None

    async def resolve_owner(self, owner: str) -> tuple[uuid.UUID, PrincipalType] | None:
        """Resolve an owner name to its principal id and type."""
        if self.users is not None:
            for user in self.users.items.values():
                if user.lower_name == owner.lower():
                    return user.id, PrincipalType.USER
        if self.organizations is not None:
            for organization in self.organizations.items.values():
                if organization.lower_name == owner.lower():
                    return organization.id, PrincipalType.ORGANIZATION
        return None

    async def get_by_owner(self, owner_id: uuid.UUID, offset: int = 0, limit: int = 100) -> list[Repository]:
        """Get all repositories owned by a principal."""
        repositories = [repository for repository in self.items.values() if repository.owner_id == owner_id]
        return [self._hydrate(repository) for repository in repositories[offset : offset + limit]]

    async def list_by_fork_of(self, fork_of_id: uuid.UUID, offset: int = 0, limit: int = 100) -> list[Repository]:
        """Get all repositories forked from a given repository."""
        repositories = [repository for repository in self.items.values() if repository.fork_of_id == fork_of_id]
        return [self._hydrate(repository) for repository in repositories[offset : offset + limit]]

    async def count_by_fork_of(self, fork_of_id: uuid.UUID) -> int:
        """Count repositories forked from a given repository."""
        return sum(1 for repository in self.items.values() if repository.fork_of_id == fork_of_id)


class FakeIssueStore(FakeCrudStore[Issue], IssueStore):
    """In-memory issue store."""

    def __init__(self, users: FakeUserStore | None = None) -> None:
        """Initialize the store."""
        super().__init__()
        self.users = users

    def _hydrate(self, issue: Issue) -> Issue:
        """Populate the issue's author from the fake user store."""
        if self.users is not None:
            author = self.users.items.get(issue.author_id)
            if author is not None:
                issue.author = author
        return issue

    async def add(self, obj: Issue) -> None:
        """Add an issue and populate its relationships."""
        self.persist(obj)
        self._hydrate(obj)

    async def get_by_number(self, repo_id: uuid.UUID, number: int) -> Issue | None:
        """Get an issue by repository id and number."""
        issue = next(
            (issue for issue in self.items.values() if issue.repo_id == repo_id and issue.number == number),
            None,
        )
        return self._hydrate(issue) if issue is not None else None

    async def list_by_repo(self, repo_id: uuid.UUID, state: IssueState | None = None) -> list[Issue]:
        """List issues for a repository, newest first."""
        issues = [issue for issue in self.items.values() if issue.repo_id == repo_id]
        if state is not None:
            issues = [issue for issue in issues if issue.state == state]
        return [self._hydrate(issue) for issue in sorted(issues, key=lambda issue: issue.number, reverse=True)]

    async def count_by_state(self, repo_id: uuid.UUID, state: IssueState) -> int:
        """Count issues in a repository by state."""
        return sum(1 for issue in self.items.values() if issue.repo_id == repo_id and issue.state == state)

    async def next_number(self, repo_id: uuid.UUID) -> int:
        """Get the next issue number for a repository."""
        numbers = [issue.number for issue in self.items.values() if issue.repo_id == repo_id]
        return (max(numbers) if numbers else 0) + 1


class FakePullRequestStore(FakeCrudStore[PullRequest], PullRequestStore):
    """In-memory pull request store."""

    def __init__(self, users: FakeUserStore | None = None) -> None:
        """Initialize the store."""
        super().__init__()
        self.users = users

    def _hydrate(self, pr: PullRequest) -> PullRequest:
        """Populate the pull request's author from the fake user store."""
        if self.users is not None:
            author = self.users.items.get(pr.author_id)
            if author is not None:
                pr.author = author
        return pr

    async def add(self, obj: PullRequest) -> None:
        """Add a pull request, applying the has_merged default."""
        obj.has_merged = bool(obj.has_merged)
        self.persist(obj)
        self._hydrate(obj)

    async def get_by_number(self, repo_id: uuid.UUID, number: int) -> PullRequest | None:
        """Get a pull request by repository id and number."""
        pr = next(
            (pr for pr in self.items.values() if pr.repo_id == repo_id and pr.number == number),
            None,
        )
        return self._hydrate(pr) if pr is not None else None

    async def list_by_repo(self, repo_id: uuid.UUID, state: IssueState | None = None) -> list[PullRequest]:
        """List pull requests for a repository, newest first."""
        pull_requests = [pr for pr in self.items.values() if pr.repo_id == repo_id]
        if state is not None:
            pull_requests = [pr for pr in pull_requests if pr.state == state]
        return [self._hydrate(pr) for pr in sorted(pull_requests, key=lambda pr: pr.number, reverse=True)]

    async def count_by_state(self, repo_id: uuid.UUID, state: IssueState) -> int:
        """Count pull requests in a repository by state."""
        return sum(1 for pr in self.items.values() if pr.repo_id == repo_id and pr.state == state)

    async def count_by_states(self, repo_id: uuid.UUID, states: list[IssueState]) -> int:
        """Count pull requests in a repository matching any of the given states."""
        return sum(1 for pr in self.items.values() if pr.repo_id == repo_id and pr.state in states)

    async def next_number(self, repo_id: uuid.UUID) -> int:
        """Get the next pull request number for a repository."""
        numbers = [pr.number for pr in self.items.values() if pr.repo_id == repo_id]
        return (max(numbers) if numbers else 0) + 1


class FakeStarStore(FakeCrudStore[Star], StarStore):
    """In-memory star store."""

    def __init__(self, users: FakeUserStore | None = None) -> None:
        """Initialize the store."""
        super().__init__()
        self.users = users

    def _hydrate(self, star: Star) -> Star:
        """Populate the star's user from the fake user store."""
        if self.users is not None:
            user = self.users.items.get(star.user_id)
            if user is not None:
                star.user = user
        return star

    async def get_by_user_and_repo(self, user_id: uuid.UUID, repo_id: uuid.UUID) -> Star | None:
        """Get a star for a user and repository, if it exists."""
        return next(
            (star for star in self.items.values() if star.user_id == user_id and star.repo_id == repo_id),
            None,
        )

    async def list_by_repo(self, repo_id: uuid.UUID, offset: int = 0, limit: int = 100) -> list[Star]:
        """List stars for a repository, newest first."""
        stars = [star for star in self.items.values() if star.repo_id == repo_id]
        stars.sort(key=lambda star: star.created_at or datetime.min.replace(tzinfo=UTC), reverse=True)
        return [self._hydrate(star) for star in stars[offset : offset + limit]]

    async def list_by_user(self, user_id: uuid.UUID, offset: int = 0, limit: int = 100) -> list[Star]:
        """List repositories starred by a user, newest first."""
        stars = [star for star in self.items.values() if star.user_id == user_id]
        stars.sort(key=lambda star: star.created_at or datetime.min.replace(tzinfo=UTC), reverse=True)
        return stars[offset : offset + limit]

    async def count_by_repo(self, repo_id: uuid.UUID) -> int:
        """Count stars for a repository."""
        return sum(1 for star in self.items.values() if star.repo_id == repo_id)


class FakeWatcherStore(FakeCrudStore[Watcher], WatcherStore):
    """In-memory watcher store."""

    def __init__(self, users: FakeUserStore | None = None) -> None:
        """Initialize the store."""
        super().__init__()
        self.users = users

    def _hydrate(self, watcher: Watcher) -> Watcher:
        """Populate the watcher's user from the fake user store."""
        if self.users is not None:
            user = self.users.items.get(watcher.user_id)
            if user is not None:
                watcher.user = user
        return watcher

    async def get_by_user_and_repo(self, user_id: uuid.UUID, repo_id: uuid.UUID) -> Watcher | None:
        """Get a watcher for a user and repository, if it exists."""
        return next(
            (watcher for watcher in self.items.values() if watcher.user_id == user_id and watcher.repo_id == repo_id),
            None,
        )

    async def list_by_repo(self, repo_id: uuid.UUID, offset: int = 0, limit: int = 100) -> list[Watcher]:
        """List watchers for a repository, newest first."""
        watchers = [watcher for watcher in self.items.values() if watcher.repo_id == repo_id]
        watchers.sort(key=lambda watcher: watcher.created_at or datetime.min.replace(tzinfo=UTC), reverse=True)
        return [self._hydrate(watcher) for watcher in watchers[offset : offset + limit]]

    async def count_by_repo(self, repo_id: uuid.UUID) -> int:
        """Count watchers for a repository."""
        return sum(1 for watcher in self.items.values() if watcher.repo_id == repo_id)


class FakeCommentStore(FakeCrudStore[Comment], CommentStore):
    """In-memory comment store."""

    def __init__(
        self,
        users: FakeUserStore | None = None,
        issues: FakeIssueStore | None = None,
        pull_requests: FakePullRequestStore | None = None,
    ) -> None:
        """Initialize the store."""
        super().__init__()
        self.users = users
        self.issues = issues
        self.pull_requests = pull_requests

    def _hydrate(self, comment: Comment) -> Comment:
        """Populate the comment's author and issue from the other fake stores."""
        if self.users is not None:
            author = self.users.items.get(comment.author_id)
            if author is not None:
                comment.author = author
        issue = None
        if self.issues is not None:
            issue = self.issues.items.get(comment.issue_id)
        if issue is None and self.pull_requests is not None:
            issue = self.pull_requests.items.get(comment.issue_id)
        if issue is not None:
            comment.issue = issue
        return comment

    async def add(self, obj: Comment) -> None:
        """Add a comment and populate its relationships."""
        self.persist(obj)
        self._hydrate(obj)

    async def list_by_issue(self, issue_id: uuid.UUID) -> list[Comment]:
        """List comments for an issue, oldest first."""
        comments = [comment for comment in self.items.values() if comment.issue_id == issue_id]
        comments.sort(key=lambda comment: comment.created_at or datetime.min.replace(tzinfo=UTC))
        return [self._hydrate(comment) for comment in comments]

    async def count_by_issue(self, issue_id: uuid.UUID) -> int:
        """Count comments for an issue."""
        return sum(1 for comment in self.items.values() if comment.issue_id == issue_id)


class FakeReleaseStore(FakeCrudStore[Release], ReleaseStore):
    """In-memory release store."""

    def __init__(self, users: FakeUserStore | None = None) -> None:
        """Initialize the store."""
        super().__init__()
        self.users = users

    def _hydrate(self, release: Release) -> Release:
        """Populate the release's author from the fake user store."""
        if self.users is not None and release.author_id is not None:
            release.author = self.users.items.get(release.author_id)
        return release

    async def add(self, obj: Release) -> None:
        """Add a release and populate its relationships."""
        self.persist(obj)
        self._hydrate(obj)

    async def list_by_repo(self, repo_id: uuid.UUID, include_drafts: bool = False) -> list[Release]:
        """List releases for a repository, newest first."""
        releases = [
            release
            for release in self.items.values()
            if release.repo_id == repo_id and (include_drafts or not release.is_draft)
        ]
        releases.sort(key=lambda release: release.created_at or datetime.min.replace(tzinfo=UTC), reverse=True)
        return [self._hydrate(release) for release in releases]

    async def get_by_tag(self, repo_id: uuid.UUID, tag_name: str) -> Release | None:
        """Get a release by repository id and tag name."""
        release = next(
            (release for release in self.items.values() if release.repo_id == repo_id and release.tag_name == tag_name),
            None,
        )
        return self._hydrate(release) if release is not None else None


class FakeActivityStore(FakeCrudStore[Activity], ActivityStore):
    """In-memory activity store."""

    def __init__(self, users: FakeUserStore | None = None, repository: FakeRepositoryStore | None = None) -> None:
        """Initialize the store."""
        super().__init__()
        self.users = users
        self.repository = repository

    def _hydrate(self, activity: Activity) -> Activity:
        """Populate the activity's actor and repository from the other fake stores."""
        if self.users is not None:
            actor = self.users.items.get(activity.actor_id)
            if actor is not None:
                activity.actor = actor
        if self.repository is not None and activity.repo_id is not None:
            repo = self.repository.items.get(activity.repo_id)
            if repo is not None:
                activity.repo = repo
        return activity

    async def add(self, obj: Activity) -> None:
        """Add an activity and populate its relationships."""
        self.persist(obj)
        self._hydrate(obj)

    def _sorted(self) -> list[Activity]:
        return sorted(
            self.items.values(),
            key=lambda activity: activity.created_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )

    async def list_recent(self, offset: int = 0, limit: int = 50) -> list[Activity]:
        """List recent activity across all repositories, newest first."""
        return [self._hydrate(activity) for activity in self._sorted()[offset : offset + limit]]

    async def list_by_repo(self, repo_id: uuid.UUID, offset: int = 0, limit: int = 50) -> list[Activity]:
        """List activity for a repository, newest first."""
        activities = [activity for activity in self._sorted() if activity.repo_id == repo_id]
        return [self._hydrate(activity) for activity in activities[offset : offset + limit]]

    async def list_by_repos(self, repo_ids: list[uuid.UUID], offset: int = 0, limit: int = 50) -> list[Activity]:
        """List activity for a set of repositories, newest first."""
        if not repo_ids:
            return []
        activities = [activity for activity in self._sorted() if activity.repo_id in repo_ids]
        return [self._hydrate(activity) for activity in activities[offset : offset + limit]]


@dataclass
class FakeStores:
    """Container for the in-memory store fakes."""

    users: FakeUserStore
    issues: FakeIssueStore
    pull_requests: FakePullRequestStore
    repository: FakeRepositoryStore
    organizations: FakeOrganizationStore
    stars: FakeStarStore
    watchers: FakeWatcherStore
    comments: FakeCommentStore
    releases: FakeReleaseStore
    activity: FakeActivityStore


@lru_cache(maxsize=1)
def _superuser_hashed_password() -> str:
    """Hash the superuser password once and reuse it across tests."""
    return get_password_hash(settings.FIRST_SUPERUSER_PASSWORD)


def build_fake_stores() -> FakeStores:
    """Create a fresh set of in-memory stores seeded with the superuser.

    Returns:
        The populated fake stores.
    """
    users = FakeUserStore()
    organizations = FakeOrganizationStore()
    repository = FakeRepositoryStore(users, organizations)
    issues = FakeIssueStore(users)
    pull_requests = FakePullRequestStore(users)
    users.persist(
        User(
            name=settings.FIRST_SUPERUSER.split("@")[0],
            lower_name=settings.FIRST_SUPERUSER.split("@")[0].lower(),
            display_name="Admin User",
            email=settings.FIRST_SUPERUSER,
            hashed_password=_superuser_hashed_password(),
            is_active=True,
            is_superuser=True,
        )
    )
    return FakeStores(
        users=users,
        issues=issues,
        pull_requests=pull_requests,
        repository=repository,
        organizations=organizations,
        stars=FakeStarStore(users),
        watchers=FakeWatcherStore(users),
        comments=FakeCommentStore(users, issues, pull_requests),
        releases=FakeReleaseStore(users),
        activity=FakeActivityStore(users, repository),
    )
