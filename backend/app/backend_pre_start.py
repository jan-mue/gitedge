from loguru import logger
from sqlalchemy.sql import select
from tenacity import retry, stop_after_attempt, wait_fixed

from app.clients.database import get_db_session

max_tries = 60 * 5  # 5 minutes
wait_seconds = 1


@retry(
    stop=stop_after_attempt(max_tries),
    wait=wait_fixed(wait_seconds),
)
def init() -> None:
    try:
        with get_db_session() as session:
            # Try to create session to check if DB is awake
            session.execute(select(1))
    except Exception as e:
        logger.error(e)
        raise e


def main() -> None:
    logger.info("Initializing service")
    init()
    logger.info("Service finished initializing")


if __name__ == "__main__":
    main()
