from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from pytest_socket import disable_socket

from app.api.dependencies import (
    check_database_connection,
    get_activity_store,
    get_blob_client,
    get_cache_client,
    get_comment_store,
    get_issue_store,
    get_organization_store,
    get_pull_request_store,
    get_redis_client,
    get_release_store,
    get_repository_store,
    get_star_store,
    get_user_store,
    get_watcher_store,
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


def pytest_runtest_setup() -> None:
    """Block network access so unit tests cannot reach real services."""
    disable_socket(allow_unix_socket=True)


@pytest.fixture(autouse=True)
def fake_stores() -> Generator[FakeStores]:
    """Override the data access stores with in-memory fakes."""
    fakes = build_fake_stores()
    app.dependency_overrides[get_user_store] = lambda: fakes.users
    app.dependency_overrides[get_issue_store] = lambda: fakes.issues
    app.dependency_overrides[get_pull_request_store] = lambda: fakes.pull_requests
    app.dependency_overrides[get_repository_store] = lambda: fakes.repository
    app.dependency_overrides[get_organization_store] = lambda: fakes.organizations
    app.dependency_overrides[get_star_store] = lambda: fakes.stars
    app.dependency_overrides[get_watcher_store] = lambda: fakes.watchers
    app.dependency_overrides[get_comment_store] = lambda: fakes.comments
    app.dependency_overrides[get_release_store] = lambda: fakes.releases
    app.dependency_overrides[get_activity_store] = lambda: fakes.activity
    app.dependency_overrides[get_cache_client] = lambda: fakes.cache
    app.dependency_overrides[get_blob_client] = lambda: fakes.blob
    app.dependency_overrides[get_redis_client] = lambda: fakes.redis

    yield fakes

    app.dependency_overrides.pop(get_user_store, None)
    app.dependency_overrides.pop(get_issue_store, None)
    app.dependency_overrides.pop(get_pull_request_store, None)
    app.dependency_overrides.pop(get_repository_store, None)
    app.dependency_overrides.pop(get_organization_store, None)
    app.dependency_overrides.pop(get_star_store, None)
    app.dependency_overrides.pop(get_watcher_store, None)
    app.dependency_overrides.pop(get_comment_store, None)
    app.dependency_overrides.pop(get_release_store, None)
    app.dependency_overrides.pop(get_activity_store, None)
    app.dependency_overrides.pop(get_cache_client, None)
    app.dependency_overrides.pop(get_blob_client, None)
    app.dependency_overrides.pop(get_redis_client, None)


@pytest.fixture
def crud(fake_stores: FakeStores) -> CrudService:
    """Provide a CRUD service backed by the fake user store."""
    return CrudService(fake_stores.users, fake_stores.organizations)


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
