"""Release store for database operations."""

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING

from app.clients.database import CrudStore, SQLStore
from app.entities.releases import Release

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ReleaseStore(CrudStore[Release], ABC):
    """Abstract release store."""


class SQLReleaseStore(ReleaseStore, SQLStore[Release]):
    """SQLAlchemy implementation of the release store."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the release store.

        Args:
            db: SQLAlchemy async session.
        """
        super().__init__(db, Release)
