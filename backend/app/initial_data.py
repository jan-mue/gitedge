"""Create initial data in the database."""

import asyncio
import logging

from app.clients.database import create_db_engine, create_session_factory
from app.utils.database import init_db

logger = logging.getLogger(__name__)


async def init() -> None:
    """Initialize the database with any required initial data."""
    async with create_db_engine() as engine:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            await init_db(session)


def main() -> None:
    """Populate the database with initial data."""
    logger.info("Creating initial data")
    asyncio.run(init())
    logger.info("Initial data created")


if __name__ == "__main__":
    main()
