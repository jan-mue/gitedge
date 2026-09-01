"""Create initial data in the database."""

import logging

from app.clients.database import get_db_session
from app.utils.database import init_db

logger = logging.getLogger(__name__)


def init() -> None:
    """Initialize the database with any required initial data."""
    with get_db_session() as session:
        init_db(session)


def main() -> None:
    """Populate the database with initial data."""
    logger.info("Creating initial data")
    init()
    logger.info("Initial data created")


if __name__ == "__main__":
    main()
