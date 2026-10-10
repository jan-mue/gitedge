"""Repository store for database operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, cast

from sqlalchemy import Table, delete, func, or_, select, update
from sqlalchemy.orm import selectinload

from app.clients.database import CrudStore, SQLStore
from app.entities.activity import Activity
from app.entities.comments import Comment
from app.entities.issues import Issue
from app.entities.principals import Principal, PrincipalType
from app.entities.pull_requests import PullRequest
from app.entities.releases import Release
from app.entities.repositories import Repository
from app.entities.stars import Star
from app.entities.watchers import Watcher
from app.exceptions import OwnerNotFoundError, RepositoryNotFoundError

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.base import ExecutableOption


class RepositoryStore(CrudStore[Repository], ABC):
    """Abstract repository store with additional repository-specific methods."""

    @abstractmethod
    async def get_by_owner_and_name(self, owner: str, name: str, *, include_releases: bool = False) -> Repository:
        """Get a repository by its owner name (user or organization) and name, raising when absent."""

    @abstractmethod
    async def find_by_owner_and_name(
        self, owner: str, name: str, *, include_releases: bool = False
    ) -> Repository | None:
        """Find a repository by its owner name (user or organization) and name, or None."""

    @abstractmethod
    async def resolve_owner(self, owner: str) -> tuple[uuid.UUID, PrincipalType]:
        """Resolve an owner name to its principal id and type, raising when absent."""

    @abstractmethod
    async def get_by_owner(self, owner_id: uuid.UUID, offset: int = 0, limit: int = 100) -> list[Repository]:
        """Get all repositories owned by a principal."""

    @abstractmethod
    async def list_by_fork_of(self, fork_of_id: uuid.UUID, offset: int = 0, limit: int = 100) -> list[Repository]:
        """Get all repositories forked from a given repository."""

    @abstractmethod
    async def count_by_fork_of(self, fork_of_id: uuid.UUID) -> int:
        """Count repositories forked from a given repository."""

    @abstractmethod
    async def count_forks_by_repos(self, repo_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Count forks for multiple repositories, keyed by repository id."""


class SQLRepositoryStore(RepositoryStore, SQLStore[Repository]):
    """SQLAlchemy implementation of repository store."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the repository store.

        Args:
            db: SQLAlchemy async session.
        """
        super().__init__(db, Repository)

    @staticmethod
    def _owner_options(include_releases: bool = False) -> tuple[ExecutableOption, ...]:
        """Eager-load options for the repository owner (and fork parent)."""
        options: list[ExecutableOption] = [
            selectinload(Repository.owner),
            selectinload(Repository.fork_of).selectinload(Repository.owner),
        ]
        if include_releases:
            options.append(selectinload(Repository.releases).selectinload(Release.author))
        return tuple(options)

    async def delete(self, obj: Repository) -> None:
        """Delete dependent records in one transaction and detach surviving forks.

        Args:
            obj: Repository to delete.
        """
        related_prs = select(PullRequest.id).where(
            or_(PullRequest.head_repo_id == obj.id, PullRequest.base_repo_id == obj.id)
        )
        issue_ids = list(
            await self.db.scalars(select(Issue.id).where(or_(Issue.repo_id == obj.id, Issue.id.in_(related_prs))))
        )
        await self.db.execute(delete(Comment).where(Comment.issue_id.in_(issue_ids)))
        # Delete the joined subclass table before its issue records.
        await self.db.execute(
            delete(cast(Table, PullRequest.__table__)).where(PullRequest.__table__.c.id.in_(issue_ids))
        )
        await self.db.execute(delete(cast(Table, Issue.__table__)).where(Issue.__table__.c.id.in_(issue_ids)))
        for entity in (Star, Watcher, Activity, Release):
            await self.db.execute(delete(entity).where(entity.repo_id == obj.id))
        await self.db.execute(update(Repository).where(Repository.fork_of_id == obj.id).values(fork_of_id=None))
        await self.db.execute(delete(Repository).where(Repository.id == obj.id))
        await self.db.commit()

    async def find(self, primary_key: uuid.UUID) -> Repository | None:
        """Find a repository by primary key with its owner loaded.

        Args:
            primary_key: Primary key of the repository.
        """
        return await self.db.scalar(
            select(Repository).options(*self._owner_options()).where(Repository.id == primary_key)
        )

    async def get_all(self, offset: int = 0, limit: int = 100) -> list[Repository]:
        """Get all repositories with their owners loaded."""
        result = await self.db.scalars(select(Repository).options(*self._owner_options()).offset(offset).limit(limit))
        return list(result.all())

    async def find_by_owner_and_name(
        self, owner: str, name: str, *, include_releases: bool = False
    ) -> Repository | None:
        """Find a repository by its owner name and name, or None."""
        stmt = (
            select(Repository)
            .options(*self._owner_options(include_releases))
            .join(Principal, Repository.owner_id == Principal.id)
            .where(Principal.lower_name == owner.lower(), Repository.name == name)
        )
        return await self.db.scalar(stmt)

    async def get_by_owner_and_name(self, owner: str, name: str, *, include_releases: bool = False) -> Repository:
        """Get a repository by its owner name and name, raising when absent."""
        repository = await self.find_by_owner_and_name(owner, name, include_releases=include_releases)
        if repository is None:
            raise RepositoryNotFoundError
        return repository

    async def resolve_owner(self, owner: str) -> tuple[uuid.UUID, PrincipalType]:
        """Resolve an owner name to its principal id and type, raising when absent."""
        principal = await self.db.scalar(select(Principal).where(Principal.lower_name == owner.lower()))
        if principal is None:
            raise OwnerNotFoundError
        return principal.id, principal.principal_type

    async def get_by_owner(self, owner_id: uuid.UUID, offset: int = 0, limit: int = 100) -> list[Repository]:
        """Get all repositories owned by a principal."""
        result = await self.db.scalars(
            select(Repository)
            .options(*self._owner_options())
            .where(Repository.owner_id == owner_id)
            .offset(offset)
            .limit(limit)
        )
        return list(result.all())

    async def list_by_fork_of(self, fork_of_id: uuid.UUID, offset: int = 0, limit: int = 100) -> list[Repository]:
        """Get all repositories forked from a given repository."""
        result = await self.db.scalars(
            select(Repository)
            .options(*self._owner_options())
            .where(Repository.fork_of_id == fork_of_id)
            .order_by(Repository.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.all())

    async def count_by_fork_of(self, fork_of_id: uuid.UUID) -> int:
        """Count repositories forked from a given repository."""
        result = await self.db.execute(
            select(func.count()).select_from(Repository).where(Repository.fork_of_id == fork_of_id)
        )
        return result.scalar_one()

    async def count_forks_by_repos(self, repo_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Count forks for multiple repositories, keyed by repository id."""
        if not repo_ids:
            return {}
        result = await self.db.execute(
            select(Repository.fork_of_id, func.count())
            .where(Repository.fork_of_id.in_(repo_ids))
            .group_by(Repository.fork_of_id)
        )
        return dict(result.all())
