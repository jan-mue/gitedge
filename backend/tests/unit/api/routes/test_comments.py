"""Tests for issue and pull request comment routes."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from tests.unit.utils.fakes import FakeStores

REPO_OWNER = settings.FIRST_SUPERUSER.split("@")[0]
REPO_NAME = "repo"
REPO_URL = f"{settings.API_V1_STR}/repositories/{REPO_OWNER}/{REPO_NAME}"
ISSUES_URL = f"{REPO_URL}/issues"
PULLS_URL = f"{REPO_URL}/pulls"
COMMENTS_URL = f"{ISSUES_URL}/1/comments"
COMMENT_URL = f"{settings.API_V1_STR}/comments"


def test_create_and_list_issue_comment(
    client: TestClient,
    fake_stores: FakeStores,
    superuser_token_headers: dict[str, str],
) -> None:
    client.post(ISSUES_URL, headers=superuser_token_headers, json={"title": "Title"})

    r = client.post(COMMENTS_URL, headers=superuser_token_headers, json={"body": "Hello there"})
    assert r.status_code == 201
    comment = r.json()
    assert comment["body"] == "Hello there"
    assert comment["author_username"] == REPO_OWNER
    assert len(fake_stores.comments.items) == 1

    r = client.get(COMMENTS_URL)
    assert r.status_code == 200
    assert r.json()["count"] == 1


def test_create_pull_request_comment(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    client.post(
        PULLS_URL,
        headers=superuser_token_headers,
        json={"title": "Pull", "head_branch": "feature"},
    )

    r = client.post(COMMENTS_URL, headers=superuser_token_headers, json={"body": "LGTM"})
    assert r.status_code == 201
    assert r.json()["body"] == "LGTM"


def test_comment_on_missing_issue(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    r = client.post(COMMENTS_URL, headers=superuser_token_headers, json={"body": "Nope"})
    assert r.status_code == 404


def test_update_comment(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    client.post(ISSUES_URL, headers=superuser_token_headers, json={"title": "Title"})
    created = client.post(COMMENTS_URL, headers=superuser_token_headers, json={"body": "Original"}).json()

    r = client.patch(
        f"{COMMENT_URL}/{created['id']}",
        headers=superuser_token_headers,
        json={"body": "Updated"},
    )
    assert r.status_code == 200
    assert r.json()["body"] == "Updated"

    listed = client.get(COMMENTS_URL).json()
    assert listed["count"] == 1
    assert listed["data"][0]["body"] == "Updated"


async def test_update_comment_requires_authorship(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    client.post(ISSUES_URL, headers=superuser_token_headers, json={"title": "Title"})
    created = client.post(COMMENTS_URL, headers=superuser_token_headers, json={"body": "Mine"}).json()

    r = client.patch(
        f"{COMMENT_URL}/{created['id']}",
        headers=normal_user_token_headers,
        json={"body": "Hijacked"},
    )
    assert r.status_code == 403


def test_update_missing_comment(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    client.post(ISSUES_URL, headers=superuser_token_headers, json={"title": "Title"})

    r = client.patch(
        f"{COMMENT_URL}/{uuid.uuid4()}",
        headers=superuser_token_headers,
        json={"body": "Nope"},
    )
    assert r.status_code == 404


def test_delete_comment(
    client: TestClient,
    fake_stores: FakeStores,
    superuser_token_headers: dict[str, str],
) -> None:
    client.post(ISSUES_URL, headers=superuser_token_headers, json={"title": "Title"})
    created = client.post(COMMENTS_URL, headers=superuser_token_headers, json={"body": "Delete me"}).json()

    r = client.delete(f"{COMMENT_URL}/{created['id']}", headers=superuser_token_headers)
    assert r.status_code == 204
    assert len(fake_stores.comments.items) == 0

    listed = client.get(COMMENTS_URL).json()
    assert listed["count"] == 0


def test_delete_comment_requires_authorship(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    client.post(ISSUES_URL, headers=superuser_token_headers, json={"title": "Title"})
    created = client.post(COMMENTS_URL, headers=superuser_token_headers, json={"body": "Mine"}).json()

    r = client.delete(f"{COMMENT_URL}/{created['id']}", headers=normal_user_token_headers)
    assert r.status_code == 403


def test_delete_missing_comment(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    r = client.delete(f"{COMMENT_URL}/{uuid.uuid4()}", headers=superuser_token_headers)
    assert r.status_code == 404
