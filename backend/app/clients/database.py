"""Database client using SQLAlchemy with PostgreSQL over asyncio."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.entities.base import Base

if TYPE_CHECKING:
    import uuid
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def create_db_engine() -> AsyncIterator[AsyncEngine]:
    """Create a database engine bound to the context's lifetime.

    Yields:
        SQLAlchemy AsyncEngine instance, disposed when the context exits.
    """
    engine = create_async_engine(str(settings.DATABASE_URL), echo=False)
    try:
        yield engine
    finally:
        await engine.dispose()


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the given engine.

    Args:
        engine: The async engine to bind sessions to.

    Returns:
        Async session factory.
    """
    return async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


class CrudStore[T: Base](ABC):
    """Abstract base class for CRUD store operations."""

    @abstractmethod
    async def get(self, primary_key: uuid.UUID) -> T | None:
        """Get an entity by its primary key."""

    @abstractmethod
    async def get_all(self, offset: int = 0, limit: int = 100) -> list[T]:
        """Get all entities with pagination."""

    @abstractmethod
    async def count(self) -> int:
        """Count all entities."""

    @abstractmethod
    async def add(self, obj: T) -> None:
        """Add a new entity."""

    @abstractmethod
    async def update(self, obj: T, new_data: dict[str, Any] | None = None) -> None:
        """Update an existing entity."""

    @abstractmethod
    async def delete(self, obj: T) -> None:
        """Delete an entity."""

    @abstractmethod
    async def refresh(self, obj: T) -> None:
        """Refresh an entity from the database."""


class SQLStore[T: Base](CrudStore[T]):
    """SQLAlchemy implementation of an async CRUD store."""

    def __init__(self, db: AsyncSession, entity_class: type[T]) -> None:
        """Initialize the store.

        Args:
            db: SQLAlchemy async session.
            entity_class: The entity class this store manages.
        """
        self.db = db
        self.entity_class = entity_class

    async def get(self, primary_key: uuid.UUID) -> T | None:
        """Get an entity by its primary key.

        Args:
            primary_key: Primary key of the entity.
        """
        return await self.db.scalar(select(self.entity_class).where(self.entity_class.id == primary_key))

    async def get_all(self, offset: int = 0, limit: int = 100) -> list[T]:
        """Get all entities with pagination."""
        result = await self.db.scalars(select(self.entity_class).offset(offset).limit(limit))
        return list(result.all())

    async def count(self) -> int:
        """Count all entities."""
        result = await self.db.execute(select(func.count()).select_from(self.entity_class))
        return result.scalar_one()

    async def add(self, obj: T) -> None:
        """Add a new entity."""
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)

    async def update(self, obj: T, new_data: dict[str, Any] | None = None) -> None:
        """Update an existing entity."""
        if new_data:
            for key, value in new_data.items():
                setattr(obj, key, value)
        await self.db.commit()

    async def delete(self, obj: T) -> None:
        """Delete an entity."""
        await self.db.delete(obj)
        await self.db.commit()

    async def refresh(self, obj: T) -> None:
        """Refresh an entity from the database."""
        await self.db.refresh(obj)
