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
