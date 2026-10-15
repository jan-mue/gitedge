"""Review API workflows using in-memory stores and a server diff fixture."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.config import settings
from app.schemas.repositories import CommitFileChange, CompareResult, DiffHunk, DiffLine, DiffToken
from app.services.repositories import RepositoryService

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from pytest_mock import MockerFixture

OWNER = settings.FIRST_SUPERUSER.split("@")[0]
URL = f"{settings.API_V1_STR}/repositories/{OWNER}/repo/pulls"
BASE = "a" * 40
HEAD = "b" * 40
COMMENT = {"path": "code.py", "side": "new", "line": 2, "body": "Please handle this case."}
DRAFT = {"base_commit": BASE, "head_commit": HEAD, "body": "Review summary", "comments": [COMMENT]}


@pytest.fixture
def comparison(mocker: MockerFixture) -> CompareResult:
    comparison = CompareResult(
        base_commit=BASE,
        head_commit=HEAD,
        files=[
            CommitFileChange(
                path="code.py",
                change_type="modify",
                additions=1,
                deletions=1,
                patch="",
                hunks=[
                    DiffHunk(
                        header="@@ -1 +2 @@",
                        lines=[
                            DiffLine(kind="delete", old_line=1, tokens=[DiffToken(text="old")]),
                            DiffLine(kind="add", new_line=2, tokens=[DiffToken(text="new")]),
                        ],
                        rows=[],
                    )
                ],
            )
        ],
        additions=1,
        deletions=1,
    )
    mocker.patch.object(RepositoryService, "compare", return_value=comparison)
    return comparison


@pytest.fixture
def pull(client: TestClient, superuser_token_headers: dict[str, str], comparison: CompareResult) -> str:  # noqa: ARG001
    response = client.post(
        URL, headers=superuser_token_headers, json={"title": "Change code", "head_branch": "feature"}
    )
    assert response.status_code == 201
    return f"{URL}/{response.json()['number']}"


def test_private_drafts_and_viewed_progress_publish_together_on_submission(
    client: TestClient, pull: str, normal_user_token_headers: dict[str, str], superuser_token_headers: dict[str, str]
) -> None:
    headers = normal_user_token_headers
    saved = client.put(f"{pull}/review-draft", headers=headers, json=DRAFT)
    assert saved.status_code == 200
    assert saved.json()["draft"] == DRAFT
    assert client.get(f"{pull}/reviews").json() == []
    assert client.get(f"{pull}/review-workspace", headers=superuser_token_headers).json()["draft"] is None
    marked = client.put(
        f"{pull}/reviewed-files",
        headers=headers,
        json={"base_commit": BASE, "head_commit": HEAD, "path": "code.py", "reviewed": True},
    )
    assert marked.status_code == 200
    assert marked.json()["reviewed_paths"] == ["code.py"]
    workspace = client.get(f"{pull}/review-workspace", headers=headers)
    assert workspace.headers["cache-control"] == "private, no-store"
    assert workspace.json()["draft"]["comments"] == [COMMENT]
    submitted = client.post(f"{pull}/reviews", headers=headers, json={**DRAFT, "state": "approved"})
    assert submitted.status_code == 201
    assert submitted.json()["state"] == "approved"
    assert submitted.json()["comments"] == [COMMENT]
    assert client.get(f"{pull}/reviews").json() == [submitted.json()]
    workspace = client.get(f"{pull}/review-workspace", headers=headers).json()
    assert workspace == {"draft": None, "reviewed_paths": ["code.py"]}


def test_authors_cannot_approve_even_as_superuser(
    client: TestClient, pull: str, superuser_token_headers: dict[str, str]
) -> None:
    response = client.post(f"{pull}/reviews", headers=superuser_token_headers, json={**DRAFT, "state": "approved"})
    assert response.status_code == 403
    assert client.get(f"{pull}/reviews").json() == []


@pytest.mark.parametrize("state", ["comment", "changes_requested"])
def test_review_outcomes_allow_author_comments(
    client: TestClient, pull: str, superuser_token_headers: dict[str, str], state: str
) -> None:
    response = client.post(f"{pull}/reviews", headers=superuser_token_headers, json={**DRAFT, "state": state})
    assert response.status_code == 201
    assert response.json()["state"] == state


@pytest.mark.parametrize(
    "comment",
    [
        {**COMMENT, "line": 999},
        {**COMMENT, "side": "old"},
        {**COMMENT, "path": "missing.py"},
        {**COMMENT, "body": "  "},
    ],
)
def test_invalid_line_comments_cannot_be_saved(
    client: TestClient, pull: str, normal_user_token_headers: dict[str, str], comment: dict[str, str | int]
) -> None:
    response = client.put(
        f"{pull}/review-draft", headers=normal_user_token_headers, json={**DRAFT, "comments": [comment]}
    )
    assert response.status_code == 422


def test_old_side_comments_are_supported(
    client: TestClient, pull: str, normal_user_token_headers: dict[str, str]
) -> None:
    old_comment = {**COMMENT, "side": "old", "line": 1}
    response = client.post(
        f"{pull}/reviews",
        headers=normal_user_token_headers,
        json={**DRAFT, "comments": [old_comment], "state": "comment"},
    )
    assert response.status_code == 201
    assert response.json()["comments"] == [old_comment]


def test_revision_changes_preserve_draft_reset_progress_and_reject_submission(
    client: TestClient, pull: str, normal_user_token_headers: dict[str, str], comparison: CompareResult
) -> None:
    headers = normal_user_token_headers
    client.put(f"{pull}/review-draft", headers=headers, json=DRAFT)
    client.put(
        f"{pull}/reviewed-files",
        headers=headers,
        json={"base_commit": BASE, "head_commit": HEAD, "path": "code.py", "reviewed": True},
    )
    comparison.head_commit = "c" * 40
    workspace = client.get(f"{pull}/review-workspace", headers=headers).json()
    assert workspace["draft"] == DRAFT
    assert workspace["reviewed_paths"] == []
    response = client.post(f"{pull}/reviews", headers=headers, json={**DRAFT, "state": "approved"})
    assert response.status_code == 409
    assert client.get(f"{pull}/reviews").json() == []


def test_closed_prs_cannot_be_reviewed(
    client: TestClient, pull: str, superuser_token_headers: dict[str, str], normal_user_token_headers: dict[str, str]
) -> None:
    client.patch(pull, headers=superuser_token_headers, json={"state": "closed"})
    response = client.post(f"{pull}/reviews", headers=normal_user_token_headers, json={**DRAFT, "state": "approved"})
    assert response.status_code == 409


def test_workspace_requires_authentication(client: TestClient, pull: str) -> None:
    assert client.get(f"{pull}/review-workspace").status_code == 401


def test_empty_comment_review_is_rejected(
    client: TestClient, pull: str, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{pull}/reviews",
        headers=normal_user_token_headers,
        json={**DRAFT, "comments": [], "body": " ", "state": "comment"},
    )
    assert response.status_code == 422


def test_pr_file_metadata_is_not_http_cached(client: TestClient, pull: str) -> None:
    response = client.get(f"{pull}/files?include_diff=false")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    repository = pull.split("/pulls/", maxsplit=1)[0]
    response = client.get(f"{repository}/compare?base=main&head=feature&include_diff=false")
    assert response.headers["cache-control"] == "no-store"
    response = client.get(f"{repository}/compare?base={BASE}&head={HEAD}&include_diff=false")
    assert "immutable" in response.headers["cache-control"]
