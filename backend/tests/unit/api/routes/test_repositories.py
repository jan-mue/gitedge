from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.config import settings
from app.utils.cache_headers import CACHE_CONTROL_PRIVATE, CACHE_CONTROL_REVALIDATE

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from tests.unit.utils.fakes import FakeStores

REPO_OWNER = settings.FIRST_SUPERUSER.split("@")[0]
REPO_NAME = "repo"
REPO_URL = f"{settings.API_V1_STR}/repositories/{REPO_OWNER}/{REPO_NAME}"
ISSUES_URL = f"{REPO_URL}/issues"
PULLS_URL = f"{REPO_URL}/pulls"
REPOSITORIES_URL = f"{settings.API_V1_STR}/repositories/"


def test_repository_settings_and_deletion(
    client: TestClient, superuser_token_headers: dict[str, str], fake_stores: FakeStores
) -> None:
    client.post(REPOSITORIES_URL, json={"owner": REPO_OWNER, "name": REPO_NAME})
    client.post(ISSUES_URL, headers=superuser_token_headers, json={"title": "Tracked issue"})
    assert client.patch(REPO_URL, json={"description": "Anonymous"}).status_code == 401
    response = client.patch(
        REPO_URL, headers=superuser_token_headers, json={"name": "renamed", "description": "Updated"}
    )
    assert response.status_code == 200
    assert response.json()["description"] == "Updated"
    assert response.json()["name"] == "renamed"
    assert client.get(REPO_URL).status_code == 404
    renamed = f"{settings.API_V1_STR}/repositories/{REPO_OWNER}/renamed"
    assert client.get(f"{renamed}/issues").json()["count"] == 1
    assert client.delete(renamed).status_code == 401
    assert client.delete(renamed, headers=superuser_token_headers).status_code == 204
    assert client.get(renamed).status_code == 404
    assert not fake_stores.issues.items


def test_repository_settings_require_owner(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    client.post(REPOSITORIES_URL, json={"owner": REPO_OWNER, "name": REPO_NAME})
    assert client.delete(REPO_URL, headers=normal_user_token_headers).status_code == 403
    response = client.patch(REPO_URL, headers=normal_user_token_headers, json={"description": "Denied"})
    assert response.status_code == 403
    assert client.patch(REPO_URL, headers=superuser_token_headers, json={"name": "../invalid"}).status_code == 422
    assert client.patch(REPO_URL, headers=superuser_token_headers, json={"name": ".git"}).status_code == 400


def test_empty_repository_statistics_and_missing_content(client: TestClient) -> None:
    client.post(REPOSITORIES_URL, json={"owner": REPO_OWNER, "name": REPO_NAME})
    response = client.get(f"{REPO_URL}/statistics")
    assert response.status_code == 200
    assert response.json() == {"commit_count": 0, "size": 0, "languages": []}
    assert response.headers["cache-control"] == CACHE_CONTROL_REVALIDATE
    assert client.get(f"{REPO_URL}/files").json() == {"paths": []}
    for endpoint in ("source", "blame", "raw"):
        response = client.get(f"{REPO_URL}/{endpoint}", params={"file_path": "missing.txt"})
        assert response.status_code == 404


@pytest.mark.parametrize("url", [ISSUES_URL, PULLS_URL])
def test_description_markdown_is_rendered(
    client: TestClient, superuser_token_headers: dict[str, str], url: str
) -> None:
    body = "# Description\n\n**bold** and ~~removed~~"
    payload = {"title": "Title", "body": body}
    if url == PULLS_URL:
        payload["head_branch"] = "feature"

    created = client.post(url, headers=superuser_token_headers, json=payload)
    assert created.status_code == 201
    expected_html = "<h1>Description</h1>\n<p><strong>bold</strong> and <s>removed</s></p>\n"
    assert created.json()["body"] == body
    assert created.json()["body_html"] == expected_html

    retrieved = client.get(f"{url}/1")
    assert retrieved.status_code == 200
    assert retrieved.json()["body_html"] == expected_html
    listed = client.get(url)
    assert listed.status_code == 200
    assert listed.json()["data"][0]["body_html"] == expected_html

    updated = client.patch(f"{url}/1", headers=superuser_token_headers, json={"body": "*Updated*"})
    assert updated.status_code == 200
    assert updated.json()["body"] == "*Updated*"
    assert updated.json()["body_html"] == "<p><em>Updated</em></p>\n"
    assert client.get(f"{url}/1").json()["body_html"] == "<p><em>Updated</em></p>\n"


@pytest.mark.parametrize("url", [ISSUES_URL, PULLS_URL])
@pytest.mark.parametrize("body", [None, ""])
def test_empty_description_has_empty_html(
    client: TestClient, superuser_token_headers: dict[str, str], url: str, body: str | None
) -> None:
    payload = {"title": "Title", "body": body, "head_branch": "feature"}
    response = client.post(url, headers=superuser_token_headers, json=payload)
    assert response.status_code == 201
    assert response.json()["body"] == body
    assert response.json()["body_html"] == ""


def test_repository_metadata_sets_cache_headers(client: TestClient) -> None:
    client.post(REPOSITORIES_URL, json={"owner": REPO_OWNER, "name": REPO_NAME})

    r = client.get(REPO_URL)
    assert r.status_code == 200
    assert r.headers["cache-control"] == CACHE_CONTROL_REVALIDATE


def test_private_repository_is_not_cached(client: TestClient, fake_stores: FakeStores) -> None:
    client.post(REPOSITORIES_URL, json={"owner": REPO_OWNER, "name": REPO_NAME})
    entity = next(iter(fake_stores.repository.items.values()))
    entity.is_private = True

    r = client.get(REPO_URL)
    assert r.status_code == 200
    assert r.headers["cache-control"] == CACHE_CONTROL_PRIVATE


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
    assert issue["repo_owner"] == REPO_OWNER
    assert issue["repo_name"] == REPO_NAME
    assert issue["author_username"] == REPO_OWNER

    assert await fake_stores.repository.get_by_owner_and_name(REPO_OWNER, REPO_NAME) is not None
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

    r = client.patch(f"{ISSUES_URL}/1", headers=superuser_token_headers, json={"state": "closed"})
    assert r.status_code == 200
    assert r.json()["state"] == "closed"


@pytest.mark.usefixtures("fake_stores")
def test_update_issue_invalid_state(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    client.post(ISSUES_URL, headers=superuser_token_headers, json={"title": "Title"})

    r = client.patch(f"{ISSUES_URL}/1", headers=superuser_token_headers, json={"state": "merged"})
    assert r.status_code == 400


@pytest.mark.usefixtures("fake_stores")
def test_update_issue_title_and_body(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    client.post(ISSUES_URL, headers=superuser_token_headers, json={"title": "Title", "body": "Body"})

    r = client.patch(
        f"{ISSUES_URL}/1", headers=superuser_token_headers, json={"title": "New title", "body": "New body"}
    )
    assert r.status_code == 200
    assert r.json()["title"] == "New title"
    assert r.json()["body"] == "New body"


def test_update_issue_requires_authorship(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    client.post(ISSUES_URL, headers=superuser_token_headers, json={"title": "Title"})

    r = client.patch(f"{ISSUES_URL}/1", headers=normal_user_token_headers, json={"title": "Hijacked"})
    assert r.status_code == 403

    r = client.patch(f"{ISSUES_URL}/1", headers=normal_user_token_headers, json={"state": "closed"})
    assert r.status_code == 200


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
    client.patch(f"{PULLS_URL}/2", headers=superuser_token_headers, json={"state": "merged"})

    r = client.get(PULLS_URL)
    assert r.status_code == 200

    payload = r.json()
    assert payload["count"] == 2
    assert payload["open_count"] == 1
    assert payload["closed_count"] == 1
