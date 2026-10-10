"""Tests for activity and profile routes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from app.config import settings
from app.entities.activity import Activity, ActivityKind, ActivityTargetType
from app.schemas.repository_activity import GitActivityCommit, GitActivityHistory

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from pytest_mock import MockerFixture

    from tests.unit.utils.fakes import FakeStores

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


def test_activity_statistics_period_and_complete_event_totals(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    fake_stores: FakeStores,
    mocker: MockerFixture,
) -> None:
    client.post(ISSUES_URL, headers=superuser_token_headers, json={"title": "New issue"})
    event = next(iter(fake_stores.activity.items.values()))
    now = datetime.now(UTC)
    # More than a page of events must still be counted; a repeated close is one issue.
    for number in range(2, 63):
        fake_stores.activity.persist(
            Activity(
                actor_id=event.actor_id,
                repo_id=event.repo_id,
                kind=ActivityKind.ISSUE_CLOSE,
                target_type=ActivityTargetType.ISSUE,
                target_number=number,
                created_at=now - timedelta(days=2),
            )
        )
    fake_stores.activity.persist(
        Activity(
            actor_id=event.actor_id,
            repo_id=event.repo_id,
            kind=ActivityKind.ISSUE_CLOSE,
            target_type=ActivityTargetType.ISSUE,
            target_number=2,
            created_at=now - timedelta(days=2),
        )
    )
    history = GitActivityHistory(
        default_branch="develop",
        commits=[
            GitActivityCommit(
                sha="a" * 40,
                message="Recent change",
                author="Author",
                author_email="author@example.com",
                timestamp=int((now - timedelta(hours=2)).timestamp()),
                is_default=True,
                is_merge=False,
                additions=3,
                deletions=1,
                files=["file.txt"],
            ),
            GitActivityCommit(
                sha="b" * 40,
                message="Older branch change",
                author="Author",
                author_email="author@example.com",
                timestamp=int((now - timedelta(days=2)).timestamp()),
                is_default=False,
                is_merge=False,
                files=["other.txt"],
            ),
            GitActivityCommit(
                sha="c" * 40,
                message="Historical change",
                author="Author",
                author_email="author@example.com",
                timestamp=int((now - timedelta(days=120)).timestamp()),
                is_default=True,
                is_merge=False,
                additions=5,
                files=["historical.txt"],
            ),
        ],
    )
    mocker.patch("app.services.repositories.RepositoryService.activity_history", return_value=history)
    week = client.get(f"{ACTIVITY_URL}/statistics?days=7")
    assert week.status_code == 200
    payload = week.json()
    assert payload["default_branch"] == "develop"
    assert payload["overview"]["closed_issues"] == 61
    assert payload["overview"]["active_issues"] == 62
    assert payload["overview"]["commits"] == 1
    assert payload["overview"]["branch_commits"] == 2
    assert payload["overview"]["files_changed"] == 1
    assert payload["overview"]["additions"] == 3
    assert sum(point["commits"] for point in payload["daily_commits"]) == 1
    assert len(payload["daily_commits"]) == 8
    assert len(payload["contributors"]) == 1
    day = client.get(f"{ACTIVITY_URL}/statistics?days=1").json()
    assert day["overview"]["closed_issues"] == 0
    assert day["overview"]["branch_commits"] == 1
    assert day["contributors"] == payload["contributors"]
    half_year = client.get(f"{ACTIVITY_URL}/statistics?days=180").json()
    assert half_year["overview"]["commits"] == 2
    assert half_year["overview"]["branch_commits"] == 3
    assert half_year["overview"]["additions"] == 8
    assert half_year["overview"]["files_changed"] == 2
    assert sum(point["commits"] for point in half_year["daily_commits"]) == 2
    assert half_year["recent_commits"] == payload["recent_commits"]
    assert sum(point["commits"] for point in payload["recent_commits"]) == 2


def test_activity_statistics_missing_repository_and_invalid_period(client: TestClient) -> None:
    assert client.get(f"{settings.API_V1_STR}/repositories/missing/repo/activity/statistics").status_code == 404
    assert client.get(f"{ACTIVITY_URL}/statistics?days=0").status_code == 422
    assert client.get(f"{ACTIVITY_URL}/statistics?days=366").status_code == 422


def test_activity_statistics_unique_merges_before_display_limit(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    fake_stores: FakeStores,
    mocker: MockerFixture,
) -> None:
    client.post(ISSUES_URL, headers=superuser_token_headers, json={"title": "Create repository"})
    seed = next(iter(fake_stores.activity.items.values()))
    now = datetime.now(UTC)
    for number in range(1, 13):
        fake_stores.activity.persist(
            Activity(
                actor_id=seed.actor_id,
                repo_id=seed.repo_id,
                kind=ActivityKind.PULL_REQUEST_MERGE,
                target_type=ActivityTargetType.PULL_REQUEST,
                target_number=number,
                title=f"Pull request {number}",
                created_at=now - timedelta(hours=number),
            )
        )
    for minutes in [1, 2]:
        fake_stores.activity.persist(
            Activity(
                actor_id=seed.actor_id,
                repo_id=seed.repo_id,
                kind=ActivityKind.PULL_REQUEST_MERGE,
                target_type=ActivityTargetType.PULL_REQUEST,
                target_number=1,
                title=f"Updated title {minutes}",
                created_at=now - timedelta(minutes=minutes),
            )
        )
    mocker.patch(
        "app.services.repositories.RepositoryService.activity_history",
        return_value=GitActivityHistory(default_branch="main", commits=[]),
    )
    payload = client.get(f"{ACTIVITY_URL}/statistics").json()
    assert payload["overview"]["merged_prs"] == 12
    assert payload["overview"]["merge_authors"] == 1
    assert [event["target_number"] for event in payload["merged_prs"]] == list(range(1, 11))
    assert payload["merged_prs"][0]["title"] == "Updated title 1"


@pytest.mark.parametrize("days", [1, 3, 7, 30, 90, 180, 365])
def test_activity_statistics_supported_periods(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    mocker: MockerFixture,
    days: int,
) -> None:
    client.post(ISSUES_URL, headers=superuser_token_headers, json={"title": "Recent issue"})
    mocker.patch(
        "app.services.repositories.RepositoryService.activity_history",
        return_value=GitActivityHistory(default_branch="main", commits=[]),
    )
    response = client.get(f"{ACTIVITY_URL}/statistics?days={days}")
    assert response.status_code == 200
    payload = response.json()
    assert datetime.fromisoformat(payload["end"]) - datetime.fromisoformat(payload["start"]) == timedelta(days=days)
    assert len(payload["daily_commits"]) == days + 1
    assert payload["overview"]["new_issues"] == 1


def test_empty_repository_activity_statistics(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    client.post(
        f"{settings.API_V1_STR}/repositories/",
        headers=superuser_token_headers,
        json={"owner": REPO_OWNER, "name": "empty-activity"},
    )
    response = client.get(f"{settings.API_V1_STR}/repositories/{REPO_OWNER}/empty-activity/activity/statistics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["overview"]["commits"] == 0
    assert payload["contributors"] == []
    assert len(payload["recent_commits"]) >= 53
    assert all(point["commits"] == 0 for point in payload["recent_commits"])


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
