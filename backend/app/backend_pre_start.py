"""Wait for the database to become available before the app starts."""

import logging

from sqlalchemy.sql import select
from tenacity import after_log, before_log, retry, stop_after_attempt, wait_fixed

from app.clients.database import get_db_session

logger = logging.getLogger(__name__)

max_tries = 60 * 5  # 5 minutes
wait_seconds = 1


@retry(
    stop=stop_after_attempt(max_tries),
    wait=wait_fixed(wait_seconds),
    before=before_log(logger, logging.INFO),
    after=after_log(logger, logging.WARNING),
)
def init() -> None:
    """Check that the database is reachable, retrying until it is."""
    try:
        with get_db_session() as session:
            # Try to create session to check if DB is awake
            session.execute(select(1))
    except Exception as e:
        logger.error(e)
        raise e


def main() -> None:
    """Initialize the service by waiting for the database."""
    logger.info("Initializing service")
    init()
    logger.info("Service finished initializing")


if __name__ == "__main__":
    main()
