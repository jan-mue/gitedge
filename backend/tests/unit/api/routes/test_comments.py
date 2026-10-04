"""Tests for issue and pull request comment routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from tests.unit.utils.fakes import FakeStores

REPO_PATH = "owner/repo.git"
ISSUES_URL = f"{settings.API_V1_STR}/repositories/{REPO_PATH}/issues"
PULLS_URL = f"{settings.API_V1_STR}/repositories/{REPO_PATH}/pulls"
COMMENTS_URL = f"{ISSUES_URL}/1/comments"


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
    assert comment["issue_number"] == 1
    assert comment["author_email"] == settings.FIRST_SUPERUSER
    assert comment["author_username"] == "admin"
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
