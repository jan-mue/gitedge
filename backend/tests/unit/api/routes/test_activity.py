"""Tests for activity and profile routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

REPO_OWNER = settings.FIRST_SUPERUSER.split("@")[0]
REPO_NAME = "repo"
REPO_URL = f"{settings.API_V1_STR}/repositories/{REPO_OWNER}/{REPO_NAME}"
ISSUES_URL = f"{REPO_URL}/issues"
FEED_URL = f"{settings.API_V1_STR}/users/me/feed"
ACTIVITY_URL = f"{REPO_URL}/activity"
PROFILE_URL = f"{settings.API_V1_STR}/users/{REPO_OWNER}"
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
    assert payload["data"][0]["repo_owner"] == REPO_OWNER
    assert payload["data"][0]["repo_name"] == REPO_NAME


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
    assert r.json()["name"] == REPO_OWNER
    assert r.json()["principal_type"] == "user"

    repos = client.get(PROFILE_REPOS_URL)
    assert repos.status_code == 200
    assert repos.json()["count"] == 1
    assert repos.json()["data"][0]["name"] == REPO_NAME

    starred = client.get(PROFILE_STARRED_URL)
    assert starred.status_code == 200
    assert starred.json()["count"] == 0


def test_organization_profile_has_no_starred(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    created = client.post(
        f"{settings.API_V1_STR}/organizations/", headers=superuser_token_headers, json={"name": "acme"}
    )
    assert created.status_code == 201

    profile = client.get(f"{settings.API_V1_STR}/users/acme")
    assert profile.status_code == 200
    assert profile.json()["principal_type"] == "organization"

    starred = client.get(f"{settings.API_V1_STR}/users/acme/starred")
    assert starred.status_code == 404


def test_profile_unknown_username(client: TestClient) -> None:
    r = client.get(f"{settings.API_V1_STR}/users/missing")
    assert r.status_code == 404
