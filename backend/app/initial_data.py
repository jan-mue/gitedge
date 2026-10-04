"""Create initial data in the database."""

import asyncio
import logging

from app.clients.database import get_db_session
from app.utils.database import init_db

logger = logging.getLogger(__name__)


async def init() -> None:
    """Initialize the database with any required initial data."""
    async with get_db_session() as session:
        await init_db(session)


def main() -> None:
    """Populate the database with initial data."""
    logger.info("Creating initial data")
    asyncio.run(init())
    logger.info("Initial data created")


if __name__ == "__main__":
    main()
