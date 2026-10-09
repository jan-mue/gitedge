"""Tests for repository release routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from tests.unit.utils.fakes import FakeStores

REPO_OWNER = settings.FIRST_SUPERUSER.split("@")[0]
REPO_NAME = "repo"
RELEASES_URL = f"{settings.API_V1_STR}/repositories/{REPO_OWNER}/{REPO_NAME}/releases"


def test_create_and_list_releases(
    client: TestClient,
    fake_stores: FakeStores,
    superuser_token_headers: dict[str, str],
) -> None:
    r = client.post(
        RELEASES_URL,
        headers=superuser_token_headers,
        json={"tag_name": "v1.0.0", "name": "First", "body": "Notes"},
    )
    assert r.status_code == 201
    release = r.json()
    assert release["tag_name"] == "v1.0.0"
    assert release["name"] == "First"
    assert release["author_username"] == REPO_OWNER
    assert len(fake_stores.releases.items) == 1

    r = client.get(RELEASES_URL)
    assert r.status_code == 200
    assert r.json()["count"] == 1


def test_duplicate_release_tag(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    body = {"tag_name": "v1.0.0"}
    client.post(RELEASES_URL, headers=superuser_token_headers, json=body)

    r = client.post(RELEASES_URL, headers=superuser_token_headers, json=body)
    assert r.status_code == 409


def test_get_release_by_tag(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    client.post(RELEASES_URL, headers=superuser_token_headers, json={"tag_name": "v2.0.0"})

    r = client.get(f"{RELEASES_URL}/v2.0.0")
    assert r.status_code == 200
    assert r.json()["tag_name"] == "v2.0.0"


def test_update_release(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    client.post(RELEASES_URL, headers=superuser_token_headers, json={"tag_name": "v1.0.0", "name": "First"})

    r = client.patch(
        f"{RELEASES_URL}/v1.0.0",
        headers=superuser_token_headers,
        json={"name": "Renamed", "body": "New notes"},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"
    assert r.json()["body"] == "New notes"


def test_update_release_requires_authorship(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    client.post(RELEASES_URL, headers=superuser_token_headers, json={"tag_name": "v1.0.0"})

    r = client.patch(
        f"{RELEASES_URL}/v1.0.0",
        headers=normal_user_token_headers,
        json={"name": "Hijacked"},
    )
    assert r.status_code == 403


def test_update_missing_release(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    r = client.patch(
        f"{RELEASES_URL}/v9.9.9",
        headers=superuser_token_headers,
        json={"name": "Nope"},
    )
    assert r.status_code == 404
