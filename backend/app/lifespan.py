"""Application lifespan handlers for shared resources."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, TypedDict

from app.clients.database import create_db_engine, create_session_factory

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


class LifespanState(TypedDict):
    """Shared resources created on startup and exposed via ``request.state``."""

    db_engine: AsyncEngine
    db_session_factory: async_sessionmaker[AsyncSession]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[LifespanState]:
    """Create shared resources on startup and release them on shutdown.

    Args:
        _app: The FastAPI application.

    Yields:
        The lifespan state made available to requests.
    """
    async with create_db_engine() as engine:
        yield {
            "db_engine": engine,
            "db_session_factory": create_session_factory(engine),
        }
