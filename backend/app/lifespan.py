"""Application lifespan handlers for shared resources."""

from __future__ import annotations

from contextlib import AsyncExitStack, asynccontextmanager
from typing import TYPE_CHECKING, TypedDict

from redis_fastapi import redis_lifespan

from app.clients.cache import uses_redis_cache
from app.clients.database import create_db_engine, create_session_factory
from app.clients.qstash import ActionsQueue, QStashClient
from app.config import settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class LifespanState(TypedDict):
    """Shared resources created on startup and exposed via ``request.state``."""

    db_session_factory: async_sessionmaker[AsyncSession]
    actions_queue: ActionsQueue


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[LifespanState]:
    """Create shared resources on startup and release them on shutdown.

    Args:
        app: The FastAPI application.

    Yields:
        The lifespan state made available to requests.
    """
    async with AsyncExitStack() as stack:
        if uses_redis_cache():
            await stack.enter_async_context(redis_lifespan(app))
        engine = await stack.enter_async_context(create_db_engine())
        queue = QStashClient()
        stack.push_async_callback(queue.close)
        if settings.QSTASH_TOKEN:
            await queue.recover_later()
        yield {
            "db_session_factory": create_session_factory(engine),
            "actions_queue": queue,
        }
