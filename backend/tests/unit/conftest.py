from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import sqlalchemy
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db, get_issue_store, get_pull_request_store, get_repository_store
from app.clients.users import SQLUserStore
from app.config import settings
from app.entities.base import Base
from app.index import app
from app.services.crud import CrudService
from app.utils.database import init_db
from tests.unit.utils.fakes import (
    FakeIssueStore,
    FakePullRequestStore,
    FakeRepositories,
    FakeRepositoryStore,
)
from tests.unit.utils.user import authentication_token_from_email
from tests.unit.utils.utils import get_superuser_token_headers

if TYPE_CHECKING:
    from collections.abc import Generator

# Create a shared test engine using StaticPool to share the in-memory database
# This ensures all connections use the same in-memory database
_test_engine = sqlalchemy.create_engine(
    "sqlite:///:memory:",
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(_test_engine)


@pytest.fixture(scope="session", autouse=True)
def init_test_db() -> Generator[None]:
    """Initialize the test database with seed data."""
    with Session(_test_engine) as session:
        init_db(session)
        yield


@pytest.fixture(scope="module")
def db() -> Generator[Session]:
    """Provide a database session for tests."""
    with Session(_test_engine) as session:
        yield session


def override_get_db() -> Generator[Session]:
    """Override the get_db dependency for tests."""
    with Session(_test_engine) as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")
def crud(db: Session) -> CrudService:
    user_store = SQLUserStore(db)
    return CrudService(user_store)


@pytest.fixture(scope="module")
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def fake_repositories() -> Generator[FakeRepositories]:
    """Override the repository clients with in-memory fakes."""
    fakes = FakeRepositories(
        issues=FakeIssueStore(),
        pull_requests=FakePullRequestStore(),
        repositories=FakeRepositoryStore(),
    )
    app.dependency_overrides[get_issue_store] = lambda: fakes.issues
    app.dependency_overrides[get_pull_request_store] = lambda: fakes.pull_requests
    app.dependency_overrides[get_repository_store] = lambda: fakes.repositories

    yield fakes

    app.dependency_overrides.pop(get_issue_store, None)
    app.dependency_overrides.pop(get_pull_request_store, None)
    app.dependency_overrides.pop(get_repository_store, None)


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, crud: CrudService) -> dict[str, str]:
    return authentication_token_from_email(client=client, email=settings.EMAIL_TEST_USER, crud=crud)
