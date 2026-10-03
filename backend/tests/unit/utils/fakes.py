"""In-memory fakes for clients used in unit tests."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.clients.database import CrudRepository
from app.clients.email import EmailClient
from app.clients.issues import IssueRepository
from app.clients.pull_requests import PullRequestRepository
from app.clients.repositories import RepositoryRepository
from app.entities.base import Base
from app.entities.issues import Issue
from app.entities.pull_requests import PullRequest
from app.entities.repositories import Repository

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger(__name__)


class FakeEmailClient(EmailClient):
    def send_email(self, email_to: str, subject: str = "", html_content: str = "") -> None:
        logger.info("Sending email to %s with subject %s and content %s", email_to, subject, html_content)


class FakeCrudRepository[T: Base](CrudRepository[T]):
    """In-memory CRUD repository."""

    def __init__(self) -> None:
        """Initialize the repository."""
        self.items: dict[uuid.UUID, T] = {}

    def get(self, primary_key: uuid.UUID) -> T | None:
        """Get an entity by its primary key."""
        return self.items.get(primary_key)

    def get_all(self, offset: int = 0, limit: int = 100) -> list[T]:
        """Get all entities with pagination."""
        return list(self.items.values())[offset : offset + limit]

    def count(self) -> int:
        """Count all entities."""
        return len(self.items)

    def add(self, obj: T) -> None:
        """Add a new entity."""
        obj.id = uuid.uuid4()
        obj.created_at = datetime.now(UTC)
        self.items[obj.id] = obj

    def update(self, obj: T, new_data: dict[str, Any] | None = None) -> None:
        """Update an existing entity."""
        if new_data:
            for key, value in new_data.items():
                setattr(obj, key, value)
        self.items[obj.id] = obj

    def delete(self, obj: T) -> None:
        """Delete an entity."""
        self.items.pop(obj.id, None)

    def refresh(self, obj: T) -> None:
        """Refresh an entity (no-op for in-memory storage)."""


class FakeRepositoryRepository(FakeCrudRepository[Repository], RepositoryRepository):
    """In-memory repository store."""

    def get_by_path(self, path: str) -> Repository | None:
        """Get a repository by its path."""
        return next((repository for repository in self.items.values() if repository.path == path), None)

    def get_by_owner(self, owner_id: uuid.UUID, offset: int = 0, limit: int = 100) -> list[Repository]:
        """Get all repositories owned by a user."""
        repositories = [repository for repository in self.items.values() if repository.owner_id == owner_id]
        return repositories[offset : offset + limit]


class FakeIssueRepository(FakeCrudRepository[Issue], IssueRepository):
    """In-memory issue repository."""

    def get_by_number(self, repo_id: uuid.UUID, number: int) -> Issue | None:
        """Get an issue by repository id and number."""
        return next(
            (issue for issue in self.items.values() if issue.repo_id == repo_id and issue.number == number),
            None,
        )

    def list_by_repo(self, repo_id: uuid.UUID, state: str | None = None) -> list[Issue]:
        """List issues for a repository, newest first."""
        issues = [issue for issue in self.items.values() if issue.repo_id == repo_id]
        if state is not None:
            issues = [issue for issue in issues if issue.state == state]
        return sorted(issues, key=lambda issue: issue.number, reverse=True)

    def count_by_state(self, repo_id: uuid.UUID, state: str) -> int:
        """Count issues in a repository by state."""
        return sum(1 for issue in self.items.values() if issue.repo_id == repo_id and issue.state == state)

    def next_number(self, repo_id: uuid.UUID) -> int:
        """Get the next issue number for a repository."""
        numbers = [issue.number for issue in self.items.values() if issue.repo_id == repo_id]
        return (max(numbers) if numbers else 0) + 1


class FakePullRequestRepository(FakeCrudRepository[PullRequest], PullRequestRepository):
    """In-memory pull request repository."""

    def add(self, obj: PullRequest) -> None:
        """Add a pull request, applying the has_merged default."""
        obj.has_merged = bool(obj.has_merged)
        super().add(obj)

    def get_by_number(self, repo_id: uuid.UUID, number: int) -> PullRequest | None:
        """Get a pull request by repository id and number."""
        return next(
            (pr for pr in self.items.values() if pr.repo_id == repo_id and pr.number == number),
            None,
        )

    def list_by_repo(self, repo_id: uuid.UUID, state: str | None = None) -> list[PullRequest]:
        """List pull requests for a repository, newest first."""
        pull_requests = [pr for pr in self.items.values() if pr.repo_id == repo_id]
        if state is not None:
            pull_requests = [pr for pr in pull_requests if pr.state == state]
        return sorted(pull_requests, key=lambda pr: pr.number, reverse=True)

    def count_by_state(self, repo_id: uuid.UUID, state: str) -> int:
        """Count pull requests in a repository by state."""
        return sum(1 for pr in self.items.values() if pr.repo_id == repo_id and pr.state == state)

    def count_by_states(self, repo_id: uuid.UUID, states: list[str]) -> int:
        """Count pull requests in a repository matching any of the given states."""
        return sum(1 for pr in self.items.values() if pr.repo_id == repo_id and pr.state in states)

    def next_number(self, repo_id: uuid.UUID) -> int:
        """Get the next pull request number for a repository."""
        numbers = [pr.number for pr in self.items.values() if pr.repo_id == repo_id]
        return (max(numbers) if numbers else 0) + 1


@dataclass
class FakeRepositories:
    """Container for the in-memory repository fakes."""

    issues: FakeIssueRepository
    pull_requests: FakePullRequestRepository
    repositories: FakeRepositoryRepository
