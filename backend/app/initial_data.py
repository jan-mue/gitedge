from loguru import logger

from app.clients.database import get_db_session
from app.utils.database import init_db


def init() -> None:
    with get_db_session() as session:
        init_db(session)


def main() -> None:
    logger.info("Creating initial data")
    init()
    logger.info("Initial data created")


if __name__ == "__main__":
    main()
