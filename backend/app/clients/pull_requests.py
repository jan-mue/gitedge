"""Pull request store for database operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.clients.database import CrudStore, SQLStore
from app.entities.issues import Issue, IssueState
from app.entities.pull_requests import PullRequest
from app.exceptions import PullRequestNotFoundError

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class PullRequestStore(CrudStore[PullRequest], ABC):
    """Abstract pull request store with pull request-specific queries."""

    @abstractmethod
    async def get_by_number(self, repo_id: uuid.UUID, number: int) -> PullRequest:
        """Get a pull request by repository id and number, raising when absent."""

    @abstractmethod
    async def list_by_repo(self, repo_id: uuid.UUID, state: IssueState | None = None) -> list[PullRequest]:
        """List pull requests for a repository, newest first."""

    @abstractmethod
    async def count_by_state(self, repo_id: uuid.UUID, state: IssueState) -> int:
        """Count pull requests in a repository by state."""

    @abstractmethod
    async def count_by_states(self, repo_id: uuid.UUID, states: list[IssueState]) -> int:
        """Count pull requests in a repository matching any of the given states."""

    @abstractmethod
    async def next_number(self, repo_id: uuid.UUID) -> int:
        """Get the next issue or pull request number for a repository."""


class SQLPullRequestStore(PullRequestStore, SQLStore[PullRequest]):
    """SQLAlchemy implementation of the pull request store."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the pull request store.

        Args:
            db: SQLAlchemy async session.
        """
        super().__init__(db, PullRequest)

    async def get_by_number(self, repo_id: uuid.UUID, number: int) -> PullRequest:
        """Get a pull request by repository id and number, raising when absent."""
        pull_request = await self.db.scalar(
            select(PullRequest)
            .options(selectinload(PullRequest.author))
            .where(PullRequest.repo_id == repo_id, PullRequest.number == number)
        )
        if pull_request is None:
            raise PullRequestNotFoundError
        return pull_request

    async def list_by_repo(self, repo_id: uuid.UUID, state: IssueState | None = None) -> list[PullRequest]:
        """List pull requests for a repository, newest first."""
        stmt = select(PullRequest).options(selectinload(PullRequest.author)).where(PullRequest.repo_id == repo_id)
        if state is not None:
            stmt = stmt.where(PullRequest.state == state)
        stmt = stmt.order_by(PullRequest.number.desc())
        result = await self.db.scalars(stmt)
        return list(result.all())

    async def count_by_state(self, repo_id: uuid.UUID, state: IssueState) -> int:
        """Count pull requests in a repository by state."""
        result = await self.db.execute(
            select(func.count())
            .select_from(PullRequest)
            .where(PullRequest.repo_id == repo_id, PullRequest.state == state)
        )
        return result.scalar_one()

    async def count_by_states(self, repo_id: uuid.UUID, states: list[IssueState]) -> int:
        """Count pull requests in a repository matching any of the given states."""
        result = await self.db.execute(
            select(func.count())
            .select_from(PullRequest)
            .where(PullRequest.repo_id == repo_id, PullRequest.state.in_(states))
        )
        return result.scalar_one()

    async def next_number(self, repo_id: uuid.UUID) -> int:
        """Get the next issue or pull request number for a repository."""
        result = await self.db.execute(select(func.max(Issue.number)).where(Issue.repo_id == repo_id))
        max_number = result.scalar_one()
        return (max_number or 0) + 1
