from collections.abc import Generator

import pytest
import sqlalchemy
from alembic.command import upgrade
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from app.clients.items import SQLItemRepository
from app.clients.users import SQLUserRepository
from app.config import settings
from app.constants import BACKEND_DIR
from app.index import app as global_app
from app.services.crud import CrudService
from app.utils.database import init_db
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers


@pytest.fixture(scope="session")
def monkeysession() -> Generator[pytest.MonkeyPatch]:
    with pytest.MonkeyPatch.context() as mp:
        yield mp


def run_alembic_migrations() -> None:
    config = Config(BACKEND_DIR / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    upgrade(config, "head")


@pytest.fixture(scope="session", autouse=True)
def db(monkeysession: pytest.MonkeyPatch) -> Generator[Session]:
    with PostgresContainer("postgres:17", driver="psycopg") as postgres:
        connection_url = postgres.get_connection_url()
        monkeysession.setattr(settings, "DATABASE_URL", connection_url)
        engine = sqlalchemy.create_engine(connection_url)
        run_alembic_migrations()
        with Session(engine) as session:
            init_db(session)
            yield session


@pytest.fixture(scope="module")
def crud(db: Session) -> CrudService:
    user_repository = SQLUserRepository(db)
    item_repository = SQLItemRepository(db)
    return CrudService(user_repository, item_repository)


@pytest.fixture
def app() -> Generator[FastAPI]:
    yield global_app
    global_app.dependency_overrides.clear()


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture
def normal_user_token_headers(client: TestClient, crud: CrudService) -> dict[str, str]:
    return authentication_token_from_email(client=client, email=settings.EMAIL_TEST_USER, crud=crud)
