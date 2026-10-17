"""Browser-to-Git verification of repository merge policies and history."""

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import expect

from tests.integration.test_commit_history import _run_git
from tests.integration.test_diff_reviews import _create_pull, _headers, _repository

if TYPE_CHECKING:
    from pathlib import Path

    from playwright.sync_api import Page


@pytest.mark.parametrize(
    ("method", "label", "template"),
    [
        ("merge", "Create merge commit", "PR title and description"),
        ("squash", "Squash and merge", "PR title and commit details"),
        ("rebase", "Rebase and merge", "PR title"),
    ],
)
def test_merge_methods_publish_git_and_retain_pr(
    page: Page, app_url: str, tmp_path: Path, method: str, label: str, template: str
) -> None:
    """Save settings in the UI, merge, fetch the actual Git graph, and reopen archived tabs."""
    name = f"merge-method-{method}"
    source = tmp_path / name
    _, _ = _repository(source, app_url, name)
    (source / "second.txt").write_text("Second change\n")
    _run_git(source, ["add", "."])
    _run_git(source, ["commit", "-m", "Second feature commit"])
    head = _run_git(source, ["rev-parse", "HEAD"])
    _run_git(source, ["push", "origin", "feature/review"])
    _run_git(source, ["checkout", "main"])
    (source / "base.txt").write_text("Independent base update\n")
    _run_git(source, ["add", "."])
    _run_git(source, ["commit", "-m", "Advance base branch"])
    base = _run_git(source, ["rev-parse", "HEAD"])
    _run_git(source, ["push", "origin", "main"])
    _create_pull(page, app_url, name)
    page.get_by_test_id("edit-pr").click()
    page.get_by_test_id("edit-pr-body").fill("Description used for the merge message.")
    page.get_by_test_id("edit-pr-submit").click()
    expect(page.get_by_test_id("edit-pr-body")).to_have_count(0)
    page.goto(f"{app_url}/admin/{name}/settings")
    page.get_by_role("combobox", name=f"{label} message", exact=True).click()
    page.get_by_role("option", name=template, exact=True).click()
    if method == "squash":
        page.get_by_role("checkbox", name="Automatically delete the PR branch after merging", exact=True).uncheck()
    with page.expect_response(
        lambda response: (
            response.url.endswith(f"/api/v1/repositories/admin/{name}") and response.request.method == "PATCH"
        )
    ) as saved:
        page.get_by_role("button", name="Save settings", exact=True).click()
    assert saved.value.status == 200
    expect(page.get_by_role("button", name="Save settings", exact=True)).to_be_disabled()
    page.reload()
    expect(page.get_by_role("combobox", name=f"{label} message", exact=True)).to_contain_text(template)
    page.goto(f"{app_url}/admin/{name}/pulls/1")
    page.get_by_role("button", name="Choose merge method", exact=True).click()
    page.get_by_role("menuitem").filter(has_text=label).click()
    expect(page.get_by_test_id("merge-pr")).to_have_text(label)
    page.get_by_test_id("merge-pr").click()
    expect(page.get_by_test_id("pr-state")).to_have_text("Merged")
    expect(page.get_by_test_id("pr-event-pull_request_merge")).to_be_visible()
    expect(page.get_by_test_id("merge-pr")).to_have_count(0)
    expect(page.get_by_text("Pull request merged successfully", exact=True)).to_have_count(0)
    _run_git(source, ["fetch", "origin", "main"])
    merged = _run_git(source, ["rev-parse", "origin/main"])
    parents = _run_git(source, ["show", "-s", "--format=%P", merged]).split()
    assert len(parents) == (2 if method == "merge" else 1)
    if method == "merge":
        assert parents == [base, head]
        assert (
            _run_git(source, ["show", "-s", "--format=%B", merged])
            == "Review configuration changes\n\nDescription used for the merge message."
        )
    elif method == "squash":
        assert parents == [base]
        assert (
            _run_git(source, ["show", "-s", "--format=%B", merged])
            == "Review configuration changes\n\nUpdate configuration\n\nSecond feature commit"
        )
    else:
        assert _run_git(source, ["rev-parse", f"{merged}~2"]) == base
        assert _run_git(source, ["show", "-s", "--format=%B", merged]) == "Review configuration changes"
        assert _run_git(source, ["show", "-s", "--format=%an", merged]) == "Diff Tester"
    assert _run_git(source, ["show", f"{merged}:base.txt"]) == "Independent base update"
    assert _run_git(source, ["show", f"{merged}:second.txt"]) == "Second change"
    assert _run_git(source, ["show", f"{merged}:file-0000.py"]).startswith("value_0 = 42")
    remaining = _run_git(source, ["ls-remote", "--heads", "origin", "feature/review"])
    assert remaining == (f"{head}\trefs/heads/feature/review" if method == "squash" else "")
    pull_url = f"{app_url}/api/v1/repositories/admin/{name}/pulls/1"
    result = page.request.get(pull_url).json()
    assert result["has_merged"]
    assert result["merged_commit_id"] == merged
    page.reload()
    page.get_by_role("tab", name="Commits", exact=False).click()
    expect(page.get_by_test_id("pr-commits")).to_contain_text("Second feature commit")
    expect(page.get_by_test_id("pr-commits")).to_contain_text("Update configuration")
    page.get_by_role("tab", name="Files Changed", exact=False).click()
    expect(page.get_by_test_id("diff-viewer")).to_be_visible()
    with page.expect_response(
        lambda response: response.url.endswith("/reviewed-files") and response.request.method == "PUT"
    ) as marked:
        page.get_by_role("checkbox", name="Mark base.txt as viewed", exact=True).click()
    assert marked.value.status == 200
    expect(page.get_by_role("button", name="Expand base.txt", exact=True)).to_be_visible()
    workspace = page.request.get(f"{pull_url}/review-workspace", headers=_headers(page)).json()
    assert "base.txt" in workspace["reviewed_paths"]
    page.get_by_role("tab", name="Conversation", exact=True).click()
    page.get_by_test_id("comment-input").fill("Follow-up after merge.")
    page.get_by_test_id("comment-submit").click()
    expect(page.get_by_test_id("comment-input")).to_have_value("")
    assert page.request.patch(pull_url, headers=_headers(page), data={"state": "open"}).status == 409
    # Disabling a method is enforced by the server as well as the menu.
    page.goto(f"{app_url}/admin/{name}/settings")
    page.get_by_role("checkbox", name=label, exact=True).uncheck()
    with page.expect_response(
        lambda response: (
            response.url.endswith(f"/api/v1/repositories/admin/{name}") and response.request.method == "PATCH"
        )
    ) as saved:
        page.get_by_role("button", name="Save settings", exact=True).click()
    assert saved.value.status == 200
    expect(page.get_by_role("button", name="Save settings", exact=True)).to_be_disabled()
    settings = page.request.get(f"{app_url}/api/v1/repositories/admin/{name}").json()
    assert (
        settings[
            {"merge": "allow_merge_commit", "squash": "allow_squash_merge", "rebase": "allow_rebase_merge"}[method]
        ]
        is False
    )

    if method == "squash":
        created = page.request.post(
            f"{app_url}/api/v1/repositories/admin/{name}/pulls",
            headers=_headers(page),
            data={"title": "Disabled method", "head_branch": "feature/review"},
        )
        assert created.status == 201
        blocked = page.request.post(
            f"{app_url}/api/v1/repositories/admin/{name}/pulls/{created.json()['number']}/merge",
            headers=_headers(page),
            data={"method": method},
        )
        assert blocked.status == 409
        assert "disabled" in blocked.json()["detail"]


def test_conflicts_are_reported_before_merging_and_refresh_after_a_push(
    page: Page, app_url: str, tmp_path: Path
) -> None:
    """A real conflicting push disables merge; resolving it updates the preflight and permits merging."""
    name = "preflight-conflicts"
    source = tmp_path / name
    _repository(source, app_url, name)
    _run_git(source, ["checkout", "main"])
    (source / "file-0000.py").write_text("base_conflict = True\n")
    _run_git(source, ["add", "."])
    _run_git(source, ["commit", "-m", "Conflicting base update"])
    _run_git(source, ["push", "origin", "main"])
    merges: list[str] = []
    page.on(
        "request",
        lambda request: (
            merges.append(request.url) if request.method == "POST" and request.url.endswith("/merge") else None
        ),
    )
    _create_pull(page, app_url, name)
    expect(page.get_by_text("This branch has conflicts that must be resolved", exact=True)).to_be_visible()
    expect(page.get_by_role("list", name="Conflicting files")).to_contain_text("file-0000.py")
    expect(page.get_by_test_id("merge-pr")).to_be_disabled()
    assert merges == []
    url = f"{app_url}/api/v1/repositories/admin/{name}/pulls/1"
    for method, label in [("squash", "Squash and merge"), ("rebase", "Rebase and merge")]:
        page.get_by_role("button", name="Choose merge method", exact=True).click()
        page.get_by_role("menuitem").filter(has_text=label).click()
        expect(page.get_by_test_id("merge-pr")).to_have_text(label)
        expect(page.get_by_text("This branch has conflicts that must be resolved", exact=True)).to_be_visible()
        expect(page.get_by_test_id("merge-pr")).to_be_disabled()
        result = page.request.get(f"{url}/mergeability?method={method}").json()
        assert result["mergeable"] is False
        assert result["conflicting_files"] == ["file-0000.py"]
    # Resolve the branch with Git and push; the old cached conflict must not survive the new head.
    _run_git(source, ["checkout", "feature/review"])
    _run_git(source, ["merge", "-s", "ours", "main", "-m", "Resolve branch conflict"])
    _run_git(source, ["push", "origin", "feature/review"])
    page.get_by_role("button", name="Choose merge method", exact=True).click()
    page.get_by_role("menuitem").filter(has_text="Create merge commit").click()
    page.get_by_role("button", name="Check again", exact=True).click()
    expect(page.get_by_test_id("merge-pr")).to_be_enabled()
    expect(page.get_by_text("This branch has no conflicts with the base branch", exact=True)).to_be_visible()
    expect(page.get_by_role("list", name="Conflicting files")).to_have_count(0)
    assert merges == []
    page.get_by_test_id("merge-pr").click()
    expect(page.get_by_test_id("pr-state")).to_have_text("Merged")
    expect(page.get_by_test_id("pr-event-pull_request_merge")).to_be_visible()
    assert len(merges) == 1
    _run_git(source, ["fetch", "origin", "main"])
    assert len(_run_git(source, ["show", "-s", "--format=%P", "origin/main"]).split()) == 2
