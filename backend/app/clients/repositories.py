"""Repository store for database operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.clients.database import CrudRepository, SQLRepository
from app.entities.repositories import Repository

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.orm import Session


class RepositoryRepository(CrudRepository[Repository], ABC):
    """Abstract repository store with additional repository-specific methods."""

    @abstractmethod
    def get_by_path(self, path: str) -> Repository | None:
        """Get a repository by its path (e.g. 'owner/repo.git')."""

    @abstractmethod
    def get_by_owner(self, owner_id: uuid.UUID, offset: int = 0, limit: int = 100) -> list[Repository]:
        """Get all repositories owned by a user."""


class SQLRepositoryRepository(RepositoryRepository, SQLRepository[Repository]):
    """SQLAlchemy implementation of repository store."""

    def __init__(self, db: Session) -> None:
        """Initialize the repository store.

        Args:
            db: SQLAlchemy session.
        """
        super().__init__(db, Repository)

    def get_by_path(self, path: str) -> Repository | None:
        """Get a repository by its path."""
        return self.db.scalar(select(Repository).where(Repository.path == path))

    def get_by_owner(self, owner_id: uuid.UUID, offset: int = 0, limit: int = 100) -> list[Repository]:
        """Get all repositories owned by a user."""
        return list(
            self.db.scalars(select(Repository).where(Repository.owner_id == owner_id).offset(offset).limit(limit)).all()
        )
