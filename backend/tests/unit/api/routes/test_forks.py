"""Fork pagination and totals respect credential and current account access."""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from app.config import settings
from app.entities.authorization import RepositoryCollaborator
from tests.unit.api.routes.test_authorization import add_repository, add_user, headers
from tests.unit.api.routes.test_personal_access_tokens import create_token

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from tests.unit.utils.fakes import FakeStores


@pytest.mark.parametrize("transport", ["bearer", "header"])
def test_token_fork_allowlist_is_applied_before_pagination(
    client: TestClient, fake_stores: FakeStores, transport: str
) -> None:
    owner = add_user(fake_stores, "owner")
    source = add_repository(fake_stores, owner, "source")
    forks = [add_repository(fake_stores, owner, f"fork-{index}", private=False) for index in range(5)]
    for index, fork in enumerate(forks):
        fork.fork_of_id = source.id
        fork.created_at = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index)
    # Newest fork is excluded; the two selected forks are on later unfiltered pages.
    issued = create_token(
        client,
        headers(owner),
        scopes=["repository:read"],
        repository_ids=[str(source.id), str(forks[1].id), str(forks[3].id)],
    )
    token = str(issued["token"])
    auth = {"Authorization": f"Bearer {token}"} if transport == "bearer" else {"X-API-Key": token}
    url = f"{settings.API_V1_STR}/repositories/owner/source/forks"
    for offset, expected in [(0, ["fork-3"]), (1, ["fork-1"]), (2, []), (100, [])]:
        response = client.get(url, headers=auth, params={"offset": offset, "limit": 1})
        assert response.status_code == 200
        assert response.json()["count"] == 2
        assert [fork["name"] for fork in response.json()["data"]] == expected
    assert client.get(url, headers=auth, params={"limit": 0}).json() == {"data": [], "count": 2}
    source_only = create_token(client, headers(owner), scopes=["repository:read"], repository_ids=[str(source.id)])
    assert client.get(url, headers={"Authorization": f"Bearer {source_only['token']}"}).json() == {
        "data": [],
        "count": 0,
    }


async def test_fork_visibility_and_revocation_are_applied_before_pagination(
    client: TestClient, fake_stores: FakeStores
) -> None:
    owner = add_user(fake_stores, "owner")
    viewer = add_user(fake_stores, "viewer")
    source = add_repository(fake_stores, owner, "source", private=False)
    for index, name in enumerate(["granted", "public", "hidden"]):
        fork = add_repository(fake_stores, owner, name, private=name != "public")
        fork.fork_of_id = source.id
        fork.created_at = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index)
        if name == "granted":
            grant = RepositoryCollaborator(repository_id=fork.id, user_id=viewer.id, role="read")
            await fake_stores.authorization.save(grant)
    url = f"{settings.API_V1_STR}/repositories/owner/source/forks"
    for offset, expected in [(0, ["public"]), (1, ["granted"]), (2, [])]:
        response = client.get(url, headers=headers(viewer), params={"offset": offset, "limit": 1})
        assert response.status_code == 200
        assert response.json()["count"] == 2
        assert [fork["name"] for fork in response.json()["data"]] == expected
    await fake_stores.authorization.remove(grant)
    response = client.get(url, headers=headers(viewer), params={"limit": 1})
    assert response.json()["count"] == 1
    assert response.json()["data"][0]["name"] == "public"
    assert client.get(url, params={"limit": 1}).json()["count"] == 1


@pytest.mark.parametrize("query", [{"offset": -1}, {"limit": -1}])
def test_fork_pagination_rejects_negative_windows(
    client: TestClient, fake_stores: FakeStores, query: dict[str, int]
) -> None:
    owner = add_user(fake_stores, "owner")
    add_repository(fake_stores, owner, "source", private=False)
    response = client.get(f"{settings.API_V1_STR}/repositories/owner/source/forks", params=query)
    assert response.status_code == 422
