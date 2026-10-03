"""Issue repository for database operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.clients.database import CrudRepository, SQLRepository
from app.entities.issues import Issue

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.orm import Session


class IssueRepository(CrudRepository[Issue], ABC):
    """Abstract issue repository with issue-specific queries."""

    @abstractmethod
    def get_by_number(self, repo_id: uuid.UUID, number: int) -> Issue | None:
        """Get an issue by repository id and number."""

    @abstractmethod
    def list_by_repo(self, repo_id: uuid.UUID, state: str | None = None) -> list[Issue]:
        """List issues for a repository, newest first."""

    @abstractmethod
    def count_by_state(self, repo_id: uuid.UUID, state: str) -> int:
        """Count issues in a repository by state."""

    @abstractmethod
    def next_number(self, repo_id: uuid.UUID) -> int:
        """Get the next issue or pull request number for a repository."""


class SQLIssueRepository(IssueRepository, SQLRepository[Issue]):
    """SQLAlchemy implementation of the issue repository."""

    def __init__(self, db: Session) -> None:
        """Initialize the issue repository.

        Args:
            db: SQLAlchemy session.
        """
        super().__init__(db, Issue)

    def get_by_number(self, repo_id: uuid.UUID, number: int) -> Issue | None:
        """Get an issue by repository id and number."""
        return self.db.scalar(
            select(Issue).where(Issue.repo_id == repo_id, Issue.number == number, Issue.kind == "issue")
        )

    def list_by_repo(self, repo_id: uuid.UUID, state: str | None = None) -> list[Issue]:
        """List issues for a repository, newest first."""
        stmt = select(Issue).where(Issue.repo_id == repo_id, Issue.kind == "issue")
        if state is not None:
            stmt = stmt.where(Issue.state == state)
        stmt = stmt.order_by(Issue.number.desc())
        return list(self.db.scalars(stmt).all())

    def count_by_state(self, repo_id: uuid.UUID, state: str) -> int:
        """Count issues in a repository by state."""
        return self.db.execute(
            select(func.count())
            .select_from(Issue)
            .where(Issue.repo_id == repo_id, Issue.kind == "issue", Issue.state == state)
        ).scalar_one()

    def next_number(self, repo_id: uuid.UUID) -> int:
        """Get the next issue or pull request number for a repository."""
        max_number = self.db.execute(select(func.max(Issue.number)).where(Issue.repo_id == repo_id)).scalar_one()
        return (max_number or 0) + 1
