"""Database client using SQLAlchemy with PostgreSQL."""

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.entities.base import Base

if TYPE_CHECKING:
    import uuid

logger = logging.getLogger(__name__)

_engine: Engine | None = None


def get_engine() -> Engine:
    """Get or create SQLAlchemy engine from DATABASE_URL.

    Returns:
        SQLAlchemy Engine instance.
    """
    global _engine  # noqa: PLW0603
    if _engine is None:
        _engine = create_engine(str(settings.DATABASE_URL), echo=False)
    return _engine


def get_db_session() -> Session:
    """Get a database session.

    Returns:
        SQLAlchemy Session instance.
    """
    engine = get_engine()
    return Session(autocommit=False, autoflush=False, bind=engine)


class CrudStore[T: Base](ABC):
    """Abstract base class for CRUD store operations."""

    @abstractmethod
    def get(self, primary_key: uuid.UUID) -> T | None:
        """Get an entity by its primary key."""

    @abstractmethod
    def get_all(self, offset: int = 0, limit: int = 100) -> list[T]:
        """Get all entities with pagination."""

    @abstractmethod
    def count(self) -> int:
        """Count all entities."""

    @abstractmethod
    def add(self, obj: T) -> None:
        """Add a new entity."""

    @abstractmethod
    def update(self, obj: T, new_data: dict[str, Any] | None = None) -> None:
        """Update an existing entity."""

    @abstractmethod
    def delete(self, obj: T) -> None:
        """Delete an entity."""

    @abstractmethod
    def refresh(self, obj: T) -> None:
        """Refresh an entity from the database."""


class SQLStore[T: Base](CrudStore[T]):
    """SQLAlchemy implementation of a CRUD store."""

    def __init__(self, db: Session, entity_class: type[T]) -> None:
        """Initialize the store.

        Args:
            db: SQLAlchemy session.
            entity_class: The entity class this store manages.
        """
        self.db = db
        self.entity_class = entity_class

    def get(self, primary_key: uuid.UUID) -> T | None:
        """Get an entity by its primary key.

        Args:
            primary_key: Primary key of the entity.
        """
        return self.db.scalar(select(self.entity_class).where(self.entity_class.id == primary_key))

    def get_all(self, offset: int = 0, limit: int = 100) -> list[T]:
        """Get all entities with pagination."""
        return list(self.db.scalars(select(self.entity_class).offset(offset).limit(limit)).all())

    def count(self) -> int:
        """Count all entities."""
        return self.db.execute(select(func.count()).select_from(self.entity_class)).scalar_one()

    def add(self, obj: T) -> None:
        """Add a new entity."""
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)

    def update(self, obj: T, new_data: dict[str, Any] | None = None) -> None:
        """Update an existing entity."""
        if new_data:
            for key, value in new_data.items():
                setattr(obj, key, value)
        self.db.commit()

    def delete(self, obj: T) -> None:
        """Delete an entity."""
        self.db.delete(obj)
        self.db.commit()

    def refresh(self, obj: T) -> None:
        """Refresh an entity from the database."""
        self.db.refresh(obj)
