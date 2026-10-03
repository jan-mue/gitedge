"""Pull request repository for database operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.clients.database import CrudRepository, SQLRepository
from app.entities.issues import Issue
from app.entities.pull_requests import PullRequest

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.orm import Session


class PullRequestRepository(CrudRepository[PullRequest], ABC):
    """Abstract pull request repository with pull request-specific queries."""

    @abstractmethod
    def get_by_number(self, repo_id: uuid.UUID, number: int) -> PullRequest | None:
        """Get a pull request by repository id and number."""

    @abstractmethod
    def list_by_repo(self, repo_id: uuid.UUID, state: str | None = None) -> list[PullRequest]:
        """List pull requests for a repository, newest first."""

    @abstractmethod
    def count_by_state(self, repo_id: uuid.UUID, state: str) -> int:
        """Count pull requests in a repository by state."""

    @abstractmethod
    def count_by_states(self, repo_id: uuid.UUID, states: list[str]) -> int:
        """Count pull requests in a repository matching any of the given states."""

    @abstractmethod
    def next_number(self, repo_id: uuid.UUID) -> int:
        """Get the next issue or pull request number for a repository."""


class SQLPullRequestRepository(PullRequestRepository, SQLRepository[PullRequest]):
    """SQLAlchemy implementation of the pull request repository."""

    def __init__(self, db: Session) -> None:
        """Initialize the pull request repository.

        Args:
            db: SQLAlchemy session.
        """
        super().__init__(db, PullRequest)

    def get_by_number(self, repo_id: uuid.UUID, number: int) -> PullRequest | None:
        """Get a pull request by repository id and number."""
        return self.db.scalar(select(PullRequest).where(PullRequest.repo_id == repo_id, PullRequest.number == number))

    def list_by_repo(self, repo_id: uuid.UUID, state: str | None = None) -> list[PullRequest]:
        """List pull requests for a repository, newest first."""
        stmt = select(PullRequest).where(PullRequest.repo_id == repo_id)
        if state is not None:
            stmt = stmt.where(PullRequest.state == state)
        stmt = stmt.order_by(PullRequest.number.desc())
        return list(self.db.scalars(stmt).all())

    def count_by_state(self, repo_id: uuid.UUID, state: str) -> int:
        """Count pull requests in a repository by state."""
        return self.db.execute(
            select(func.count())
            .select_from(PullRequest)
            .where(PullRequest.repo_id == repo_id, PullRequest.state == state)
        ).scalar_one()

    def count_by_states(self, repo_id: uuid.UUID, states: list[str]) -> int:
        """Count pull requests in a repository matching any of the given states."""
        return self.db.execute(
            select(func.count())
            .select_from(PullRequest)
            .where(PullRequest.repo_id == repo_id, PullRequest.state.in_(states))
        ).scalar_one()

    def next_number(self, repo_id: uuid.UUID) -> int:
        """Get the next issue or pull request number for a repository."""
        max_number = self.db.execute(select(func.max(Issue.number)).where(Issue.repo_id == repo_id)).scalar_one()
        return (max_number or 0) + 1
