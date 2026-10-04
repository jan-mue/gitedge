"""Tests for repository star and watcher routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.config import settings

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from tests.unit.utils.fakes import FakeStores

REPO_PATH = "owner/repo.git"
STAR_URL = f"{settings.API_V1_STR}/repositories/{REPO_PATH}/star"
WATCH_URL = f"{settings.API_V1_STR}/repositories/{REPO_PATH}/watch"
STARGAZERS_URL = f"{settings.API_V1_STR}/repositories/{REPO_PATH}/stargazers"
WATCHERS_URL = f"{settings.API_V1_STR}/repositories/{REPO_PATH}/watchers"
STARRED_URL = f"{settings.API_V1_STR}/users/me/starred"


def test_star_and_unstar_repository(
    client: TestClient,
    fake_stores: FakeStores,
    superuser_token_headers: dict[str, str],
) -> None:
    r = client.put(STAR_URL, headers=superuser_token_headers)
    assert r.status_code == 200
    assert r.json() == {"is_starred": True, "stars_count": 1}
    assert len(fake_stores.stars.items) == 1

    state = client.get(STAR_URL, headers=superuser_token_headers)
    assert state.json()["is_starred"] is True

    r = client.delete(STAR_URL, headers=superuser_token_headers)
    assert r.status_code == 200
    assert r.json() == {"is_starred": False, "stars_count": 0}
    assert len(fake_stores.stars.items) == 0


@pytest.mark.usefixtures("fake_stores")
def test_star_state_for_unknown_repository(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    r = client.get(STAR_URL, headers=superuser_token_headers)
    assert r.status_code == 200
    assert r.json() == {"is_starred": False, "stars_count": 0}


@pytest.mark.usefixtures("fake_stores")
def test_list_stargazers(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    client.put(STAR_URL, headers=superuser_token_headers)

    r = client.get(STARGAZERS_URL)
    assert r.status_code == 200
    payload = r.json()
    assert payload["count"] == 1
    assert payload["data"][0]["email"] == settings.FIRST_SUPERUSER


@pytest.mark.usefixtures("fake_stores")
def test_list_starred_repositories(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    client.put(STAR_URL, headers=superuser_token_headers)

    r = client.get(STARRED_URL, headers=superuser_token_headers)
    assert r.status_code == 200
    payload = r.json()
    assert payload["count"] == 1
    assert payload["data"][0]["path"] == REPO_PATH


def test_watch_and_unwatch_repository(
    client: TestClient,
    fake_stores: FakeStores,
    superuser_token_headers: dict[str, str],
) -> None:
    r = client.put(WATCH_URL, headers=superuser_token_headers)
    assert r.status_code == 200
    assert r.json() == {"is_watching": True, "watchers_count": 1}
    assert len(fake_stores.watchers.items) == 1

    r = client.delete(WATCH_URL, headers=superuser_token_headers)
    assert r.status_code == 200
    assert r.json() == {"is_watching": False, "watchers_count": 0}


@pytest.mark.usefixtures("fake_stores")
def test_list_watchers(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    client.put(WATCH_URL, headers=superuser_token_headers)

    r = client.get(WATCHERS_URL)
    assert r.status_code == 200
    assert r.json()["count"] == 1
