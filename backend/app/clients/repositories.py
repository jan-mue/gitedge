"""Repository store for database operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.clients.database import CrudStore, SQLStore
from app.entities.principals import Principal, PrincipalType
from app.entities.releases import Release
from app.entities.repositories import Repository
from app.exceptions import OwnerNotFoundError, RepositoryNotFoundError

if TYPE_CHECKING:
    import uuid

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
