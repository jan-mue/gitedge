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
from app.constants import BACKEND_ROOT_DIR
from app.main import app as global_app
from app.services.crud import CrudService
from app.utils.database import init_db
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers


@pytest.fixture(scope="session")
def monkeysession() -> Generator[pytest.MonkeyPatch, None, None]:
    with pytest.MonkeyPatch.context() as mp:
        yield mp


def run_alembic_migrations() -> None:
    config = Config(BACKEND_ROOT_DIR / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_ROOT_DIR / "migrations"))
    upgrade(config, "head")


@pytest.fixture(scope="session", autouse=True)
def db(monkeysession: pytest.MonkeyPatch) -> Generator[Session, None, None]:
    with PostgresContainer("postgres:17", driver="psycopg") as postgres:
        monkeysession.setattr(
            settings, "POSTGRES_SERVER", postgres.get_container_host_ip()
        )
        monkeysession.setattr(
            settings, "POSTGRES_PORT", postgres.get_exposed_port(postgres.port)
        )
        monkeysession.setattr(settings, "POSTGRES_USER", postgres.username)
        monkeysession.setattr(settings, "POSTGRES_PASSWORD", postgres.password)
        monkeysession.setattr(settings, "POSTGRES_DB", postgres.dbname)
        connection_url = postgres.get_connection_url()
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
def app() -> Generator[FastAPI, None, None]:
    yield global_app
    global_app.dependency_overrides.clear()


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture
def normal_user_token_headers(client: TestClient, crud: CrudService) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, crud=crud
    )
