"""Repository store for database operations."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, cast, override

from sqlalchemy import Table, delete, false, func, or_, select, update
from sqlalchemy.orm import selectinload

from app.clients.authorization import repository_role_grants
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
    from sqlalchemy.sql.elements import ColumnElement

    from app.entities.users import User

logger = logging.getLogger(__name__)


class RepositoryStore(CrudStore[Repository], ABC):
    """Abstract repository store with additional repository-specific methods."""

    @abstractmethod
    async def get_by_ids(self, repository_ids: list[uuid.UUID]) -> list[Repository]:
        """Fetch a repository selection in one batch."""

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
    async def list_by_fork_of(
        self,
        fork_of_id: uuid.UUID,
        offset: int = 0,
        limit: int = 100,
        *,
        allowed_repository_ids: Sequence[uuid.UUID] | None = None,
        user: User | None = None,
        readable_roles: frozenset[str] | None = None,
    ) -> list[Repository]:
        """List forks, restricting repository IDs before applying pagination."""

    @abstractmethod
    async def count_by_fork_of(
        self,
        fork_of_id: uuid.UUID,
        *,
        allowed_repository_ids: Sequence[uuid.UUID] | None = None,
        user: User | None = None,
        readable_roles: frozenset[str] | None = None,
    ) -> int:
        """Count forks using the same access filters as the requested page."""

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

    @override
    async def delete(self, obj: Repository) -> None:
        """Delete dependent records in one transaction and detach surviving forks."""
        try:
            related_prs = select(PullRequest.id).where(
                or_(PullRequest.head_repo_id == obj.id, PullRequest.base_repo_id == obj.id)
            )
            issue_ids = list(
                await self.db.scalars(select(Issue.id).where(or_(Issue.repo_id == obj.id, Issue.id.in_(related_prs))))
            )
            await self.db.execute(delete(Comment).where(Comment.issue_id.in_(issue_ids)))
            await self.db.execute(
                delete(cast(Table, PullRequest.__table__)).where(PullRequest.__table__.c.id.in_(issue_ids))
            )
            await self.db.execute(delete(cast(Table, Issue.__table__)).where(Issue.__table__.c.id.in_(issue_ids)))
            for entity in (Star, Watcher, Activity, Release):
                await self.db.execute(delete(entity).where(entity.repo_id == obj.id))
            await self.db.execute(update(Repository).where(Repository.fork_of_id == obj.id).values(fork_of_id=None))
            await self.db.execute(delete(Repository).where(Repository.id == obj.id))
            await self.db.commit()
        except BaseException:
            logger.exception("Failed to delete repository")
            await self.db.rollback()
            raise

    @override
    async def find(self, primary_key: uuid.UUID) -> Repository | None:
        """Find a repository by primary key with its owner loaded.

        Args:
            primary_key: Primary key of the repository.
        """
        return await self.db.scalar(
            select(Repository).options(*self._owner_options()).where(Repository.id == primary_key)
        )

    @override
    async def get_all(self, offset: int = 0, limit: int = 100) -> list[Repository]:
        """Get all repositories with their owners loaded."""
        result = await self.db.scalars(select(Repository).options(*self._owner_options()).offset(offset).limit(limit))
        return list(result.all())

    @override
    async def get_by_ids(self, repository_ids: list[uuid.UUID]) -> list[Repository]:
        """Resolve a token's explicit repository selection without per-ID queries."""
        return list(await self.db.scalars(select(Repository).where(Repository.id.in_(repository_ids))))

    @override
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

    @override
    async def get_by_owner_and_name(self, owner: str, name: str, *, include_releases: bool = False) -> Repository:
        """Get a repository by its owner name and name, raising when absent."""
        repository = await self.find_by_owner_and_name(owner, name, include_releases=include_releases)
        if repository is None:
            raise RepositoryNotFoundError
        return repository

    @override
    async def resolve_owner(self, owner: str) -> tuple[uuid.UUID, PrincipalType]:
        """Resolve an owner name to its principal id and type, raising when absent."""
        principal = await self.db.scalar(select(Principal).where(Principal.lower_name == owner.lower()))
        if principal is None:
            raise OwnerNotFoundError
        return principal.id, principal.principal_type

    @override
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

    @override
    async def list_by_fork_of(
        self,
        fork_of_id: uuid.UUID,
        offset: int = 0,
        limit: int = 100,
        *,
        allowed_repository_ids: Sequence[uuid.UUID] | None = None,
        user: User | None = None,
        readable_roles: frozenset[str] | None = None,
    ) -> list[Repository]:
        """List allowed forks before pagination; an empty allowlist matches nothing."""
        statement = (
            select(Repository)
            .options(*self._owner_options())
            .where(*self._fork_filters(fork_of_id, allowed_repository_ids, user, readable_roles))
            .order_by(Repository.created_at.desc(), Repository.id.desc())
        )
        result = await self.db.scalars(statement.offset(offset).limit(limit))
        return list(result.all())

    @override
    async def count_by_fork_of(
        self,
        fork_of_id: uuid.UUID,
        *,
        allowed_repository_ids: Sequence[uuid.UUID] | None = None,
        user: User | None = None,
        readable_roles: frozenset[str] | None = None,
    ) -> int:
        """Count accessible forks in SQL without loading repositories or their owners."""
        result = await self.db.execute(
            select(func.count())
            .select_from(Repository)
            .where(*self._fork_filters(fork_of_id, allowed_repository_ids, user, readable_roles))
        )
        return result.scalar_one()

    @staticmethod
    def _fork_filters(
        fork_of_id: uuid.UUID,
        allowed_repository_ids: Sequence[uuid.UUID] | None,
        user: User | None,
        readable_roles: frozenset[str] | None,
    ) -> list[ColumnElement[bool]]:
        """Apply current grants and Casbin's readable roles before pagination and counting."""
        filters = [Repository.fork_of_id == fork_of_id]
        if allowed_repository_ids is not None:
            filters.append(Repository.id.in_(allowed_repository_ids))
        if readable_roles is None:
            return filters
        if user is not None and not user.is_active:
            return [*filters, false()]
        if user is not None and user.is_superuser and "owner" in readable_roles:
            return filters
        visibility: list[ColumnElement[bool]] = [false()]
        if "read" in readable_roles:
            visibility.append(Repository.is_private.is_(False))
        if user is not None:
            if "owner" in readable_roles:
                visibility.append(Repository.owner_id == user.id)
            grants = repository_role_grants(user.id).subquery()
            visibility.append(
                Repository.id.in_(select(grants.c.repository_id).where(grants.c.role.in_(readable_roles)))
            )
        return [*filters, or_(*visibility)]

    @override
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
