"""Tests for activity and profile routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

REPO_PATH = "owner/repo.git"
ISSUES_URL = f"{settings.API_V1_STR}/repositories/{REPO_PATH}/issues"
FEED_URL = f"{settings.API_V1_STR}/users/me/feed"
ACTIVITY_URL = f"{settings.API_V1_STR}/repositories/{REPO_PATH}/activity"
PROFILE_URL = f"{settings.API_V1_STR}/users/admin"
PROFILE_REPOS_URL = f"{PROFILE_URL}/repositories"
PROFILE_STARRED_URL = f"{PROFILE_URL}/starred"


def test_feed_contains_issue_activity(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    client.post(ISSUES_URL, headers=superuser_token_headers, json={"title": "Feed issue"})

    r = client.get(FEED_URL, headers=superuser_token_headers)
    assert r.status_code == 200
    payload = r.json()
    assert payload["count"] >= 1
    assert payload["data"][0]["kind"] == "issue_open"
    assert payload["data"][0]["title"] == "Feed issue"
    assert payload["data"][0]["repo_path"] == REPO_PATH


def test_repository_activity(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    client.post(ISSUES_URL, headers=superuser_token_headers, json={"title": "Repo issue"})

    r = client.get(ACTIVITY_URL)
    assert r.status_code == 200
    assert r.json()["count"] == 1


def test_profile_by_username(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    client.post(ISSUES_URL, headers=superuser_token_headers, json={"title": "Owned"})

    r = client.get(PROFILE_URL)
    assert r.status_code == 200
    assert r.json()["username"] == "admin"

    repos = client.get(PROFILE_REPOS_URL)
    assert repos.status_code == 200
    assert repos.json()["count"] == 1
    assert repos.json()["data"][0]["path"] == REPO_PATH

    starred = client.get(PROFILE_STARRED_URL)
    assert starred.status_code == 200
    assert starred.json()["count"] == 0


def test_profile_unknown_username(client: TestClient) -> None:
    r = client.get(f"{settings.API_V1_STR}/users/missing")
    assert r.status_code == 404
