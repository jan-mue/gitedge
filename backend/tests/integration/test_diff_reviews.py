"""Real Git, database, object storage and browser coverage for diff reviews."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

import psycopg
from playwright.sync_api import expect

from app.config import settings
from tests.integration.conftest import (
    FIRST_SUPERUSER,
    FIRST_SUPERUSER_PASSWORD,
    create_user_via_api,
    log_in_user,
)
from tests.integration.test_commit_history import _run_git

if TYPE_CHECKING:
    from pathlib import Path

    from playwright.sync_api import Page


def _repository(path: Path, app_url: str, name: str, count: int = 3, lines: int = 12) -> tuple[str, str]:
    path.mkdir()
    _run_git(path, ["init", "-b", "main"])
    _run_git(path, ["config", "user.name", "Diff Tester"])
    _run_git(path, ["config", "user.email", "diff@example.com"])
    for index in range(count):
        (path / f"file-{index:04}.py").write_text(
            "".join(f"value_{line} = 12  # configuration\n" for line in range(lines))
        )
    _run_git(path, ["add", "."])
    _run_git(path, ["commit", "-m", "Base files"])
    base = _run_git(path, ["rev-parse", "HEAD"])
    _run_git(path, ["checkout", "-b", "feature/review"])
    for index in range(count):
        (path / f"file-{index:04}.py").write_text(
            "".join(f"value_{line} = 42  # configuration\n" for line in range(lines))
        )
    _run_git(path, ["add", "."])
    _run_git(path, ["commit", "-m", "Update configuration"])
    head = _run_git(path, ["rev-parse", "HEAD"])
    _run_git(path, ["remote", "add", "origin", f"{app_url}/api/v1/admin/{name}.git"])
    _run_git(path, ["push", "origin", "main", "feature/review"])
    return base, head


def _create_pull(page: Page, app_url: str, name: str) -> None:
    log_in_user(page, app_url, FIRST_SUPERUSER, FIRST_SUPERUSER_PASSWORD)
    page.goto(f"{app_url}/admin/{name}/pulls/new")
    page.get_by_test_id("pr-source-branch").click()
    page.get_by_role("option", name="feature/review", exact=True).click()
    page.get_by_test_id("pr-title-input").fill("Review configuration changes")
    page.get_by_test_id("submit-pr-btn").click()
    page.wait_for_url(f"{app_url}/admin/{name}/pulls")
    page.get_by_role("link", name="Review configuration changes", exact=True).click()
    expect(page.get_by_test_id("pull-detail")).to_be_visible()
    page.get_by_role("tab", name="Commits", exact=False).click()
    expect(page.get_by_test_id("pr-commits")).to_be_visible()
    expect(page.get_by_role("link", name="Update configuration", exact=True)).to_be_visible()
    expect(page.get_by_role("link", name="Base files", exact=True)).not_to_be_visible()
    page.get_by_role("tab", name="Conversation", exact=True).click()


def _headers(page: Page) -> dict[str, str]:
    return {"Authorization": f"Bearer {page.evaluate('localStorage.getItem("access_token")')}"}


def test_review_lifecycle(page: Page, app_url: str, tmp_path: Path, random_email: str, random_password: str) -> None:
    """Create a PR in the UI, persist line drafts, submit all outcomes, and reject stale reviews."""
    name = "diff-review-flow"
    source = tmp_path / "source"
    base, head = _repository(source, app_url, name)
    _create_pull(page, app_url, name)
    pull = f"{app_url}/api/v1/repositories/admin/{name}/pulls/1"
    snapshot = {"base_commit": base, "head_commit": head}
    page.get_by_role("tab", name="Files Changed", exact=False).click()
    page.get_by_role("button", name="Review", exact=True).click()
    expect(page.get_by_role("button", name="Approve", exact=True)).to_be_disabled()
    response = page.request.post(f"{pull}/reviews", headers=_headers(page), data={**snapshot, "state": "approved"})
    assert response.status == 403
    page.get_by_role("button", name="Close review", exact=True).click()

    create_user_via_api(app_url, random_email, random_password)
    page.evaluate("localStorage.removeItem('access_token')")
    log_in_user(page, app_url, random_email, random_password)
    page.goto(f"{app_url}/admin/{name}/pulls/1")
    page.get_by_role("tab", name="Files Changed", exact=False).click()
    page.get_by_role("button", name="Comment on file-0000.py old line 1", exact=True).click()
    page.get_by_role("textbox", name="Line comment").fill("Please preserve the original behavior.")
    page.get_by_role("button", name="Add to review").click()
    expect(page.get_by_text("Please preserve the original behavior.", exact=True)).to_be_visible()
    page.get_by_role("checkbox", name="Mark file-0000.py as viewed").click()
    expect(page.get_by_text("1 / 3 files viewed")).to_be_visible()
    assert page.request.get(f"{pull}/reviews").json() == []
    page.reload()
    page.get_by_role("tab", name="Files Changed", exact=False).click()
    expect(page.get_by_role("button", name="Expand file-0000.py", exact=True)).to_be_visible()
    page.get_by_role("button", name="Expand file-0000.py", exact=True).click()
    expect(page.get_by_text("Please preserve the original behavior.", exact=True)).to_be_visible()
    expect(page.get_by_text("1 / 3 files viewed")).to_be_visible()

    page.get_by_role("button", name="Split", exact=True).click()
    page.get_by_role("button", name="Comment on file-0000.py new line 1", exact=True).click()
    page.get_by_role("textbox", name="Line comment").fill("Please cover this value in a test.")
    page.get_by_role("button", name="Add to review").click()
    page.get_by_role("button", name="Review (2)", exact=True).click()
    page.get_by_role("textbox", name="Review comment").fill("Two changes needed before merging.")
    page.get_by_role("button", name="Request changes", exact=True).click()
    expect(page.get_by_role("dialog")).not_to_be_visible()
    page.get_by_role("tab", name="Conversation", exact=True).click()
    expect(page.get_by_text("requested changes", exact=True)).to_be_visible()
    expect(page.get_by_text("Two changes needed before merging.", exact=True)).to_be_visible()
    thread = page.get_by_role("region", name="Review comment on file-0000.py old line 1", exact=True)
    expect(thread.get_by_text("Please preserve the original behavior.", exact=True)).to_be_visible()
    expect(thread.locator('[data-comment-anchor="true"] code')).to_contain_text("value_0 = 12")
    expect(thread.locator('[data-syntax="literal-number-integer"]').first).to_be_visible()
    expect(thread.locator(".review-diff-context .diff-cell").last).to_have_attribute("data-comment-anchor", "true")
    thread.get_by_role("button", name="Reply", exact=True).click()
    thread.get_by_role("textbox", name="Reply to review comment").fill("I added a **regression test** for this.")
    thread.get_by_role("button", name="Reply", exact=True).click()
    expect(thread.get_by_text("I added a regression test for this.", exact=True)).to_be_visible()
    expect(thread.locator(".markdown-body strong")).to_have_text("regression test")
    new_thread = page.get_by_role("region", name="Review comment on file-0000.py new line 1", exact=True)
    expect(new_thread.get_by_text("I added a regression test for this.", exact=True)).to_have_count(0)
    requested: list[str] = []
    page.on("request", lambda request: requested.append(request.url))
    page.reload()
    thread = page.get_by_role("region", name="Review comment on file-0000.py old line 1", exact=True)
    expect(thread.get_by_text("I added a regression test for this.", exact=True)).to_be_visible()
    expect(thread.locator('[data-comment-anchor="true"] code')).to_contain_text("value_0 = 12")
    assert not any(f"{pull}/{suffix}" in url for url in requested for suffix in ("files?", "commits?"))
    assert not any("/diff-file?" in url or url.endswith("/context") for url in requested)
    reviews = page.request.get(f"{pull}/reviews").json()
    assert len(reviews) == 1
    assert len(reviews[0]["comments"]) == 2
    pull_id = page.request.get(pull).json()["id"]
    with psycopg.connect(str(settings.DATABASE_URL).replace("postgresql+psycopg://", "postgresql://")) as db:
        comments = db.execute(
            "SELECT c.id, c.body, c.reply_to, pc.review_id, pc.path FROM comment c "
            "LEFT JOIN pull_request_comments pc ON pc.comment_id = c.id WHERE c.issue_id = %s",
            (pull_id,),
        ).fetchall()
    assert len(comments) == 4  # Summary, two line comments, one reply: all regular comments.
    anchor = next(comment for comment in comments if str(comment[0]) == reviews[0]["comments"][0]["id"])
    reply = next(comment for comment in comments if comment[2] is not None)
    assert reply[2] == anchor[0]
    assert str(anchor[3]) == reviews[0]["id"]
    assert anchor[4] == "file-0000.py"
    discussion = f"{app_url}/api/v1/repositories/admin/{name}/issues/1/comments"
    assert page.request.get(discussion).json()["data"] == []

    assert page.request.get(f"{pull}/review-workspace", headers=_headers(page)).json()["draft"] is None

    for button, state in [("Comment", "comment"), ("Approve", "approved")]:
        page.get_by_role("tab", name="Files Changed", exact=False).click()
        page.get_by_role("button", name="Review", exact=True).click()
        page.get_by_role("textbox", name="Review comment").fill(f"Review outcome: {state}")
        page.get_by_role("button", name=button, exact=True).click()
        expect(page.get_by_role("dialog")).not_to_be_visible()
    assert [review["state"] for review in page.request.get(f"{pull}/reviews").json()] == [
        "changes_requested",
        "comment",
        "approved",
    ]

    draft = {**snapshot, "body": "Earlier revision", "comments": []}
    assert page.request.put(f"{pull}/review-draft", headers=_headers(page), data=draft).ok
    (source / "file-0000.py").write_text("value_0 = 99\n")
    _run_git(source, ["add", "."])
    _run_git(source, ["commit", "-m", "Update PR after review"])
    _run_git(source, ["push", "origin", "feature/review"])
    assert (
        page.request.post(f"{pull}/reviews", headers=_headers(page), data={**draft, "state": "approved"}).status == 409
    )
    page.reload()
    old_thread = page.get_by_role("region", name="Review comment on file-0000.py old line 1", exact=True)
    old_thread.scroll_into_view_if_needed()
    expect(old_thread.get_by_text("Outdated", exact=True)).to_be_visible()
    expect(old_thread.locator('[data-comment-anchor="true"] code')).to_contain_text("value_0 = 12")
    expect(old_thread.get_by_text("I added a regression test for this.", exact=True)).to_be_visible()
    page.get_by_role("tab", name="Files Changed", exact=False).click()
    expect(page.get_by_text("The branches changed since you started this review.")).to_be_visible()
    expect(page.get_by_text("0 / 3 files viewed")).to_be_visible()
    page.get_by_role("button", name="Start review of current changes").click()
    expect(page.get_by_role("button", name="Review", exact=True)).to_be_enabled()
    page.evaluate("localStorage.removeItem('access_token')")
    log_in_user(page, app_url, FIRST_SUPERUSER, FIRST_SUPERUSER_PASSWORD)
    page.goto(f"{app_url}/admin/{name}/pulls/1")
    page.get_by_test_id("merge-pr").click()
    expect(page.get_by_test_id("pr-state")).to_contain_text("Merged")
    merged_thread = page.get_by_role("region", name="Review comment on file-0000.py old line 1", exact=True)
    merged_thread.get_by_role("button", name="Reply", exact=True).click()
    merged_thread.get_by_role("textbox", name="Reply to review comment").fill("Follow-up after merging.")
    merged_thread.get_by_role("button", name="Reply", exact=True).click()
    expect(merged_thread.get_by_text("Follow-up after merging.", exact=True)).to_be_visible()
    page.reload()
    expect(
        page.get_by_role("region", name="Review comment on file-0000.py old line 1", exact=True).get_by_text(
            "Follow-up after merging.", exact=True
        )
    ).to_be_visible()

    # The regular comment API removes review anchors and their replies as one thread.
    anchor_id = reviews[0]["comments"][0]["id"]
    assert page.request.delete(f"{app_url}/api/v1/comments/{anchor_id}", headers=_headers(page)).status == 204
    remaining = page.request.get(f"{pull}/reviews").json()[0]
    assert len(remaining["comments"]) == 1
    assert remaining["replies"] == []


def test_large_pr_bounds_rendering_and_fetches(page: Page, app_url: str, tmp_path: Path) -> None:
    """A 500-file PR renders and fetches the viewport, and can navigate to the final file."""
    name = "large-diff-review"
    _, head = _repository(tmp_path / "source", app_url, name, count=500, lines=40)
    _create_pull(page, app_url, name)
    files_url = f"{app_url}/api/v1/repositories/admin/{name}/pulls/1/files?include_diff=false"
    started = time.perf_counter()
    summary = page.request.get(files_url)
    summary_ms = (time.perf_counter() - started) * 1000
    assert summary.ok
    assert len(summary.body()) < 250_000
    changes = summary.json()
    assert len(changes["files"]) == 500
    assert all(not file["diff_loaded"] and file["patch"] == "" and not file["hunks"] for file in changes["files"])
    requested = []
    page.on("request", lambda request: requested.append(request.url) if "/diff-file?" in request.url else None)
    started = time.perf_counter()
    page.get_by_role("tab", name="Files Changed", exact=False).click()
    expect(page.locator('[data-syntax="literal-number-integer"][data-changed="true"]').first).to_be_visible()
    first_file_ms = (time.perf_counter() - started) * 1000
    initial_requests = len(requested)
    assert initial_requests < 10
    assert page.locator(".diff-code-row").count() < 500
    assert page.locator("*").count() < 8000
    page.locator(".diff-file-list").evaluate("element => element.scrollTop = element.scrollHeight")
    page.get_by_role("navigation", name="Changed files").get_by_role(
        "button", name="file-0499.py M", exact=False
    ).click()
    expect(page.get_by_role("region", name="Diff for file-0499.py")).to_be_visible()
    expect(page.get_by_role("region", name="Diff for file-0499.py").get_by_text("42", exact=True).first).to_be_visible()
    page.get_by_role("button", name="Split", exact=True).click()
    page.get_by_role("button", name="Wrap lines").click()
    assert page.locator(".diff-code-row").count() < 500
    page.get_by_role("textbox", name="Filter changed files").fill("file-0250")
    expect(page.get_by_role("region", name="Diff for file-0250.py")).to_be_visible()
    assert page.get_by_role("region", name="Diff for file-0250.py").count() == 1
    page.goto(f"{app_url}/admin/{name}/commit/{head}")
    expect(page.get_by_test_id("diff-viewer")).to_be_visible()
    assert page.locator(".diff-code-row").count() < 500
    page.goto(f"{app_url}/admin/{name}/compare?base=main&head=feature%2Freview")
    expect(page.get_by_test_id("diff-viewer")).to_be_visible()
    page.get_by_label("Head branch, tag, or commit").fill("main")
    page.get_by_role("button", name="Compare", exact=True).click()
    expect(page.get_by_text("No changed files in this comparison.")).to_be_visible()
    page.go_back()
    expect(page.get_by_label("Head branch, tag, or commit")).to_have_value("feature/review")
    expect(page.get_by_test_id("diff-viewer")).to_be_visible()
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("button", name="Wrap lines").click()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    print(
        json.dumps(
            {
                "files": 500,
                "summary_bytes": len(summary.body()),
                "summary_ms": round(summary_ms),
                "first_highlighted_file_ms": round(first_file_ms),
                "initial_file_requests": initial_requests,
                "dom_nodes": page.locator("*").count(),
            }
        )
    )


def test_large_file_preserves_editor_across_virtual_scroll(page: Page, app_url: str, tmp_path: Path) -> None:
    """A 10,000-row diff stays bounded without losing an in-progress line comment."""
    name = "large-single-file"
    _repository(tmp_path / "source", app_url, name, count=1, lines=5000)
    _create_pull(page, app_url, name)
    page.get_by_role("tab", name="Files Changed", exact=False).click()
    page.get_by_role("button", name="Comment on file-0000.py old line 1", exact=True).click()
    editor = page.get_by_role("textbox", name="Line comment")
    editor.fill("Keep this draft while scrolling.")
    page.evaluate("window.scrollTo(0, 50000)")
    expect(editor).to_have_value("Keep this draft while scrolling.")
    assert page.locator(".diff-code-row").count() < 200
    page.evaluate("window.scrollTo(0, 0)")
    page.get_by_role("button", name="Add to review").click()
    expect(page.get_by_text("Keep this draft while scrolling.", exact=True)).to_be_visible()
    page.get_by_role("button", name="Wrap lines").click()
    page.get_by_role("button", name="Split", exact=True).click()
    assert page.locator(".diff-code-row").count() < 200
    page.reload()
    page.get_by_role("tab", name="Files Changed", exact=False).click()
    expect(page.get_by_text("Keep this draft while scrolling.", exact=True)).to_be_visible()
    page.get_by_role("button", name="Review (1)", exact=True).click()
    page.get_by_role("button", name="Comment", exact=True).click()
    expect(page.get_by_role("dialog")).not_to_be_visible()
    requests: list[str] = []
    page.on("request", lambda request: requests.append(request.url))
    started = time.perf_counter()
    page.reload()
    thread = page.get_by_role("region", name="Review comment on file-0000.py old line 1", exact=True)
    expect(thread.get_by_text("Keep this draft while scrolling.", exact=True)).to_be_visible()
    expect(thread.locator('[data-comment-anchor="true"] code')).to_contain_text("value_0 = 12")
    assert thread.locator(".diff-code-row").count() <= 4
    assert not any("/diff-file?" in url or url.endswith("/context") for url in requests)
    assert not any(f"/pulls/1/{suffix}" in url for url in requests for suffix in ("files?", "commits?"))
    ready_ms = round((time.perf_counter() - started) * 1000)
    payload = page.request.get(f"{app_url}/api/v1/repositories/admin/{name}/pulls/1/reviews")
    assert len(payload.body()) < 10_000
    print(
        json.dumps(
            {
                "scenario": "10000-row-review-conversation",
                "ready_ms": ready_ms,
                "review_bytes": len(payload.body()),
                "git_requests": 0,
            }
        )
    )
