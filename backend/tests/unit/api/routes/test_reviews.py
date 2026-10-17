"""Review API workflows using in-memory stores and a server diff fixture."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.config import settings
from app.schemas.repositories import CommitFileChange, CompareResult, DiffHunk, DiffLine, DiffToken
from app.services.repositories import RepositoryService
from tests.unit.utils.git import seed_merge_repository

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from pytest_mock import MockerFixture

    from tests.unit.utils.fakes import FakeStores

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
    submitted_comment = submitted.json()["comments"][0]
    assert {
        key: value for key, value in submitted_comment.items() if key not in {"context", "id", "body_html"}
    } == COMMENT
    assert submitted_comment["body_html"] == "<p>Please handle this case.</p>\n"
    assert submitted_comment["context"]["lines"][-1]["new_line"] == COMMENT["line"]
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
    submitted = response.json()["comments"][0]
    assert {key: value for key, value in submitted.items() if key not in {"context", "id", "body_html"}} == old_comment
    assert len(submitted["context"]["lines"]) == 1
    assert submitted["context"]["lines"][-1]["old_line"] == 1


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


def test_replies_persist_on_their_thread_after_merging(
    client: TestClient,
    pull: str,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    fake_stores: FakeStores,
) -> None:
    seed_merge_repository(fake_stores, OWNER, "repo")
    review = client.post(
        f"{pull}/reviews", headers=normal_user_token_headers, json={**DRAFT, "state": "comment"}
    ).json()
    replies = f"{pull}/reviews/{review['id']}/replies"
    line = client.post(
        replies, headers=superuser_token_headers, json={"comment_index": 0, "body": "**Agreed** on this line."}
    )
    assert line.status_code == 201
    assert "<strong>Agreed</strong>" in line.json()["body_html"]
    assert client.patch(pull, headers=superuser_token_headers, json={"state": "merged"}).status_code == 200
    overall = client.post(replies, headers=normal_user_token_headers, json={"body": "Thanks for merging."})
    assert overall.status_code == 201
    published = client.get(f"{pull}/reviews").json()[0]
    assert published["comments"] == review["comments"]
    assert published["replies"] == [line.json(), overall.json()]
    assert published["replies"][0]["comment_index"] == 0
    assert published["replies"][1]["comment_index"] is None


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({"comment_index": 999, "body": "Invalid line"}, 404),
        ({"comment_index": -1, "body": "Invalid index"}, 422),
        ({"comment_index": 0, "body": "  "}, 422),
    ],
)
def test_invalid_replies_are_rejected(
    client: TestClient, pull: str, normal_user_token_headers: dict[str, str], body: dict[str, str | int], status: int
) -> None:
    review = client.post(
        f"{pull}/reviews", headers=normal_user_token_headers, json={**DRAFT, "state": "comment"}
    ).json()
    assert (
        client.post(f"{pull}/reviews/{review['id']}/replies", headers=normal_user_token_headers, json=body).status_code
        == status
    )
    assert client.get(f"{pull}/reviews").json()[0]["replies"] == []


def test_replies_require_authentication_and_belong_to_the_requested_pr(
    client: TestClient,
    pull: str,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    fake_stores: FakeStores,
) -> None:
    seed_merge_repository(fake_stores, OWNER, "repo")
    review = client.post(
        f"{pull}/reviews", headers=normal_user_token_headers, json={**DRAFT, "state": "comment"}
    ).json()
    suffix = f"/reviews/{review['id']}/replies"
    assert client.post(pull + suffix, json={"body": "Anonymous"}).status_code == 401
    other = client.post(URL, headers=superuser_token_headers, json={"title": "Other PR", "head_branch": "other"}).json()
    assert (
        client.post(
            f"{URL}/{other['number']}{suffix}", headers=normal_user_token_headers, json={"body": "Wrong PR"}
        ).status_code
        == 404
    )


def test_new_review_context_and_listing_do_not_recalculate_git(
    client: TestClient, pull: str, normal_user_token_headers: dict[str, str], mocker: MockerFixture
) -> None:
    review = client.post(
        f"{pull}/reviews", headers=normal_user_token_headers, json={**DRAFT, "state": "comment"}
    ).json()
    compare = mocker.patch.object(RepositoryService, "compare", side_effect=AssertionError("Unexpected comparison"))
    context = mocker.patch.object(
        RepositoryService, "get_diff_context", side_effect=AssertionError("Unexpected Git context load")
    )
    mocker.patch.object(RepositoryService, "branch_heads", return_value=(BASE, "c" * 40))
    result = client.get(f"{pull}/reviews/{review['id']}/comments/0/context")
    assert result.json() == review["comments"][0]["context"]
    assert client.get(f"{pull}/reviews").json()[0]["outdated"] is True
    compare.assert_not_called()
    context.assert_not_called()


def test_legacy_context_uses_original_revisions_and_validates_its_anchor(
    client: TestClient,
    pull: str,
    normal_user_token_headers: dict[str, str],
    fake_stores: FakeStores,
    comparison: CompareResult,
    mocker: MockerFixture,
) -> None:
    review = client.post(
        f"{pull}/reviews", headers=normal_user_token_headers, json={**DRAFT, "state": "comment"}
    ).json()
    stored = next(review for review in fake_stores.reviews.reviews.items.values())
    stored.line_comments[0].context = None
    context = mocker.patch.object(RepositoryService, "get_diff_context", return_value=comparison.files[0].hunks[0])
    url = f"{pull}/reviews/{review['id']}/comments"
    assert client.get(f"{url}/0/context").status_code == 200
    context.assert_called_once_with(OWNER, "repo", BASE, HEAD, "code.py", "new", 2)
    assert client.get(f"{url}/999/context").status_code == 404
    assert client.get(f"{url}/-1/context").status_code == 422


def test_pr_file_metadata_and_immutable_comparisons(client: TestClient, pull: str) -> None:
    response = client.get(f"{pull}/files?include_diff=false")
    assert response.status_code == 200
    repository = pull.split("/pulls/", maxsplit=1)[0]
    response = client.get(f"{repository}/compare?base=main&head=feature&include_diff=false")
    assert response.status_code == 200
    response = client.get(f"{repository}/compare?base={BASE}&head={HEAD}&include_diff=false")
    assert "immutable" in response.headers["cache-control"]


def test_review_text_and_replies_share_the_regular_comment_store(
    client: TestClient, pull: str, normal_user_token_headers: dict[str, str], fake_stores: FakeStores
) -> None:
    """Review summaries, anchors and replies use ordinary comments with stable IDs."""
    review = client.post(
        f"{pull}/reviews", headers=normal_user_token_headers, json={**DRAFT, "state": "comment"}
    ).json()
    summary_id = review["summary_comment_id"]
    anchor_id = review["comments"][0]["id"]
    comments = {str(comment.id): comment for comment in fake_stores.comments.items.values()}
    assert set(comments) == {summary_id, anchor_id}
    assert comments[summary_id].body == DRAFT["body"]
    assert comments[anchor_id].body == COMMENT["body"]
    reply = client.post(
        f"{pull}/reviews/{review['id']}/replies",
        headers=normal_user_token_headers,
        json={"reply_to": anchor_id, "body": "I will add the test."},
    )
    assert reply.status_code == 201
    assert reply.json()["reply_to"] == anchor_id
    assert reply.json()["comment_index"] == 0
    stored_reply = next(
        comment for comment in fake_stores.comments.items.values() if str(comment.id) == reply.json()["id"]
    )
    assert str(stored_reply.reply_to) == anchor_id
    discussion = pull.replace("/pulls/", "/issues/") + "/comments"
    assert client.get(discussion).json()["data"] == []
    assert (
        client.patch(
            f"{settings.API_V1_STR}/comments/{anchor_id}",
            headers=normal_user_token_headers,
            json={"body": "Updated review comment"},
        ).status_code
        == 200
    )
    published = client.get(f"{pull}/reviews").json()[0]
    assert published["comments"][0]["body"] == "Updated review comment"
    assert len(published["replies"]) == 1


def test_reply_target_cannot_cross_reviews(
    client: TestClient, pull: str, normal_user_token_headers: dict[str, str]
) -> None:
    first, second = [
        client.post(f"{pull}/reviews", headers=normal_user_token_headers, json={**DRAFT, "state": "comment"}).json()
        for _ in range(2)
    ]
    response = client.post(
        f"{pull}/reviews/{second['id']}/replies",
        headers=normal_user_token_headers,
        json={"reply_to": first["comments"][0]["id"], "body": "Wrong thread"},
    )
    assert response.status_code == 404


def test_deleting_a_review_comment_cascades_its_thread_without_retargeting_replies(
    client: TestClient, pull: str, normal_user_token_headers: dict[str, str]
) -> None:
    """Comment identities remain stable when another anchor in the review is removed."""
    review = client.post(
        f"{pull}/reviews",
        headers=normal_user_token_headers,
        json={**DRAFT, "state": "comment", "comments": [COMMENT, {**COMMENT, "side": "old", "line": 1}]},
    ).json()
    first, second = [comment["id"] for comment in review["comments"]]
    replies = f"{pull}/reviews/{review['id']}/replies"
    assert (
        client.post(
            replies, headers=normal_user_token_headers, json={"reply_to": first, "body": "First thread"}
        ).status_code
        == 201
    )
    assert (
        client.delete(f"{settings.API_V1_STR}/comments/{first}", headers=normal_user_token_headers).status_code == 204
    )
    published = client.get(f"{pull}/reviews").json()[0]
    assert [comment["id"] for comment in published["comments"]] == [second]
    assert published["replies"] == []
    reply = client.post(replies, headers=normal_user_token_headers, json={"reply_to": second, "body": "Second thread"})
    assert reply.status_code == 201
    assert reply.json()["reply_to"] == second
    assert reply.json()["comment_index"] == 0
