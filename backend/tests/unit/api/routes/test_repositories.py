from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.config import settings

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from tests.unit.utils.fakes import FakeStores

REPO_PATH = "owner/repo.git"
ISSUES_URL = f"{settings.API_V1_STR}/repositories/{REPO_PATH}/issues"
PULLS_URL = f"{settings.API_V1_STR}/repositories/{REPO_PATH}/pulls"


async def test_create_issue(
    client: TestClient,
    fake_stores: FakeStores,
    superuser_token_headers: dict[str, str],
) -> None:
    r = client.post(ISSUES_URL, headers=superuser_token_headers, json={"title": "Title", "body": "Body"})
    assert r.status_code == 201

    issue = r.json()
    assert issue["number"] == 1
    assert issue["title"] == "Title"
    assert issue["body"] == "Body"
    assert issue["state"] == "open"
    assert issue["repo_path"] == REPO_PATH
    assert issue["author_email"] == settings.FIRST_SUPERUSER

    assert await fake_stores.repository.get_by_path(REPO_PATH) is not None
    assert len(fake_stores.issues.items) == 1


@pytest.mark.usefixtures("fake_stores")
def test_list_issues(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    client.post(ISSUES_URL, headers=superuser_token_headers, json={"title": "First"})
    client.post(ISSUES_URL, headers=superuser_token_headers, json={"title": "Second"})

    r = client.get(ISSUES_URL)
    assert r.status_code == 200

    payload = r.json()
    assert [issue["number"] for issue in payload["data"]] == [2, 1]
    assert payload["count"] == 2
    assert payload["open_count"] == 2
    assert payload["closed_count"] == 0


@pytest.mark.usefixtures("fake_stores")
def test_list_issues_for_unknown_repository(client: TestClient) -> None:
    r = client.get(ISSUES_URL)
    assert r.status_code == 200
    assert r.json()["count"] == 0


@pytest.mark.usefixtures("fake_stores")
def test_get_issue(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    client.post(ISSUES_URL, headers=superuser_token_headers, json={"title": "Title"})

    r = client.get(f"{ISSUES_URL}/1")
    assert r.status_code == 200
    assert r.json()["title"] == "Title"


@pytest.mark.usefixtures("fake_stores")
def test_get_missing_issue(client: TestClient) -> None:
    r = client.get(f"{ISSUES_URL}/1")
    assert r.status_code == 404


@pytest.mark.usefixtures("fake_stores")
def test_update_issue(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    client.post(ISSUES_URL, headers=superuser_token_headers, json={"title": "Title"})

    r = client.patch(f"{ISSUES_URL}/1", json={"state": "closed"})
    assert r.status_code == 200
    assert r.json()["state"] == "closed"


@pytest.mark.usefixtures("fake_stores")
def test_update_issue_invalid_state(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    client.post(ISSUES_URL, headers=superuser_token_headers, json={"title": "Title"})

    r = client.patch(f"{ISSUES_URL}/1", json={"state": "merged"})
    assert r.status_code == 400


def test_create_pull_request(
    client: TestClient,
    fake_stores: FakeStores,
    superuser_token_headers: dict[str, str],
) -> None:
    r = client.post(
        PULLS_URL,
        headers=superuser_token_headers,
        json={"title": "Pull request", "head_branch": "feature", "base_branch": "main"},
    )
    assert r.status_code == 201

    pull_request = r.json()
    assert pull_request["number"] == 1
    assert pull_request["state"] == "open"
    assert pull_request["head_branch"] == "feature"
    assert pull_request["base_branch"] == "main"
    assert len(fake_stores.pull_requests.items) == 1


@pytest.mark.usefixtures("fake_stores")
def test_list_pull_requests_counts(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    client.post(PULLS_URL, headers=superuser_token_headers, json={"title": "First", "head_branch": "a"})
    client.post(PULLS_URL, headers=superuser_token_headers, json={"title": "Second", "head_branch": "b"})
    client.patch(f"{PULLS_URL}/2", json={"state": "merged"})

    r = client.get(PULLS_URL)
    assert r.status_code == 200

    payload = r.json()
    assert payload["count"] == 2
    assert payload["open_count"] == 1
    assert payload["closed_count"] == 1
