"""Issue store for database operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.clients.database import CrudStore, SQLStore
from app.entities.issues import Issue, IssueKind, IssueState

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class IssueStore(CrudStore[Issue], ABC):
    """Abstract issue store with issue-specific queries."""

    @abstractmethod
    async def get_by_number(self, repo_id: uuid.UUID, number: int) -> Issue | None:
        """Get an issue by repository id and number."""

    @abstractmethod
    async def list_by_repo(self, repo_id: uuid.UUID, state: IssueState | None = None) -> list[Issue]:
        """List issues for a repository, newest first."""

    @abstractmethod
    async def count_by_state(self, repo_id: uuid.UUID, state: IssueState) -> int:
        """Count issues in a repository by state."""

    @abstractmethod
    async def next_number(self, repo_id: uuid.UUID) -> int:
        """Get the next issue or pull request number for a repository."""


class SQLIssueStore(IssueStore, SQLStore[Issue]):
    """SQLAlchemy implementation of the issue store."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the issue store.

        Args:
            db: SQLAlchemy async session.
        """
        super().__init__(db, Issue)

    async def get_by_number(self, repo_id: uuid.UUID, number: int) -> Issue | None:
        """Get an issue by repository id and number."""
        return await self.db.scalar(
            select(Issue)
            .options(selectinload(Issue.author))
            .where(Issue.repo_id == repo_id, Issue.number == number, Issue.kind == IssueKind.ISSUE)
        )

    async def list_by_repo(self, repo_id: uuid.UUID, state: IssueState | None = None) -> list[Issue]:
        """List issues for a repository, newest first."""
        stmt = (
            select(Issue)
            .options(selectinload(Issue.author))
            .where(Issue.repo_id == repo_id, Issue.kind == IssueKind.ISSUE)
        )
        if state is not None:
            stmt = stmt.where(Issue.state == state)
        stmt = stmt.order_by(Issue.number.desc())
        result = await self.db.scalars(stmt)
        return list(result.all())

    async def count_by_state(self, repo_id: uuid.UUID, state: IssueState) -> int:
        """Count issues in a repository by state."""
        result = await self.db.execute(
            select(func.count())
            .select_from(Issue)
            .where(Issue.repo_id == repo_id, Issue.kind == IssueKind.ISSUE, Issue.state == state)
        )
        return result.scalar_one()

    async def next_number(self, repo_id: uuid.UUID) -> int:
        """Get the next issue or pull request number for a repository."""
        result = await self.db.execute(select(func.max(Issue.number)).where(Issue.repo_id == repo_id))
        max_number = result.scalar_one()
        return (max_number or 0) + 1
