"""Wait for the database to become available before the app starts."""

import asyncio
import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import select
from tenacity import after_log, before_log, retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from app.clients.database import create_db_engine, create_session_factory

logger = logging.getLogger(__name__)

max_tries = 60 * 5  # 5 minutes
wait_seconds = 1


@retry(
    stop=stop_after_attempt(max_tries),
    wait=wait_fixed(wait_seconds),
    retry=retry_if_exception_type(SQLAlchemyError),
    before=before_log(logger, logging.INFO),
    after=after_log(logger, logging.WARNING),
)
async def init() -> None:
    """Check that the database is reachable, retrying until it is."""
    async with create_db_engine() as engine:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            await session.execute(select(1))


def main() -> None:
    """Initialize the service by waiting for the database."""
    logger.info("Initializing service")
    asyncio.run(init())
    logger.info("Service finished initializing")


if __name__ == "__main__":
    main()
