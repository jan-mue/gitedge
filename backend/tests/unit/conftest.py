from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.api.dependencies import (
    check_database_connection,
    get_issue_store,
    get_pull_request_store,
    get_repository_store,
    get_user_store,
)
from app.config import settings
from app.index import app
from app.services.crud import CrudService
from tests.unit.utils.fakes import FakeStores, build_fake_stores
from tests.unit.utils.user import authentication_token_from_email
from tests.unit.utils.utils import get_superuser_token_headers

if TYPE_CHECKING:
    from collections.abc import Generator


app.dependency_overrides[check_database_connection] = lambda: True


@pytest.fixture(autouse=True)
def fake_stores() -> Generator[FakeStores]:
    """Override the data access stores with in-memory fakes."""
    fakes = build_fake_stores()
    app.dependency_overrides[get_user_store] = lambda: fakes.users
    app.dependency_overrides[get_issue_store] = lambda: fakes.issues
    app.dependency_overrides[get_pull_request_store] = lambda: fakes.pull_requests
    app.dependency_overrides[get_repository_store] = lambda: fakes.repository

    yield fakes

    app.dependency_overrides.pop(get_user_store, None)
    app.dependency_overrides.pop(get_issue_store, None)
    app.dependency_overrides.pop(get_pull_request_store, None)
    app.dependency_overrides.pop(get_repository_store, None)


@pytest.fixture
def crud(fake_stores: FakeStores) -> CrudService:
    """Provide a CRUD service backed by the fake user store."""
    return CrudService(fake_stores.users)


@pytest.fixture(scope="module")
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest_asyncio.fixture
async def normal_user_token_headers(client: TestClient, crud: CrudService) -> dict[str, str]:
    return await authentication_token_from_email(client=client, email=settings.EMAIL_TEST_USER, crud=crud)
