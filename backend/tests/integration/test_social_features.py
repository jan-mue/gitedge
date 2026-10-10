"""End-to-end tests for the social and forge features.

Covers the functionality ported from the Gitea-like UI: starring, watching,
forking, branches and tags, releases, issue comments, pull request comments
and merging, the activity feed, stargazers/watchers/forks listings, explore,
user profiles, and empty repositories.
"""

from __future__ import annotations

import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from playwright.sync_api import expect

from tests.integration.conftest import (
    FIRST_SUPERUSER,
    FIRST_SUPERUSER_PASSWORD,
    create_repository_row,
    create_user_via_api,
    log_in_user,
)

if TYPE_CHECKING:
    from playwright.sync_api import Page

SUPERUSER_EMAIL = FIRST_SUPERUSER
SUPERUSER_PASSWORD = FIRST_SUPERUSER_PASSWORD
SUPERUSER_USERNAME = FIRST_SUPERUSER.split("@")[0]


def _run_git(cwd: Path, args: list[str]) -> str:
    """Run a git command and return its output.

    Args:
        cwd: Working directory for the command.
        args: Git command arguments.

    Returns:
        Command stdout as string.
    """
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _push_repo(
    app_url: str,
    repo_name: str,
    *,
    extra_branches: tuple[str, ...] = (),
    tag: str | None = None,
) -> None:
    """Push a test repository with a README, a source file, optional branches and a tag.

    Args:
        app_url: Base URL of the GitEdge frontend.
        repo_name: Repository path (e.g. "testuser/repo.git").
        extra_branches: Additional branches to create and push.
        tag: Optional tag to create and push.
    """
    remote_url = f"{app_url}/{repo_name}"

    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = Path(tmpdir) / "source"
        source_dir.mkdir()

        _run_git(source_dir, ["init", "-b", "main"])
        _run_git(source_dir, ["config", "user.email", "test@example.com"])
        _run_git(source_dir, ["config", "user.name", "Test User"])

        (source_dir / "README.md").write_text("# Test Repository\n\nA test repository.\n")
        src_dir = source_dir / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text('print("Hello, World!")\n')

        _run_git(source_dir, ["add", "."])
        _run_git(source_dir, ["commit", "-m", "Initial commit"])
        if tag:
            _run_git(source_dir, ["tag", tag])

        _run_git(source_dir, ["remote", "add", "origin", remote_url])
        _run_git(source_dir, ["push", "-u", "--force", "origin", "main"])
        if tag:
            _run_git(source_dir, ["push", "--force", "origin", tag])

        for branch in extra_branches:
            _run_git(source_dir, ["checkout", "-b", branch, "main"])
            (source_dir / f"{branch.replace('/', '_')}.txt").write_text(f"{branch}\n")
            _run_git(source_dir, ["add", "."])
            _run_git(source_dir, ["commit", "-m", f"Add {branch}"])
            _run_git(source_dir, ["push", "-u", "--force", "origin", branch])
            _run_git(source_dir, ["checkout", "main"])


def _create_foreign_owner(app_url: str) -> str:
    """Create a second user and return their name, to own a repository to fork.

    Args:
        app_url: Base URL of the GitEdge frontend.

    Returns:
        The new user's name.
    """
    suffix = uuid.uuid4().hex[:8]
    user = create_user_via_api(app_url, f"forkowner-{suffix}@example.com", "password123")
    return user["name"]


class TestStarAndWatch:
    """Test the star and watch repository buttons."""

    def test_star_repository_toggles_and_updates_count(self, app_url: str, page: Page) -> None:
        """Starring increments the count and toggles the button state.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "admin/starrepo.git")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/admin/starrepo")

        star_button = page.get_by_test_id("star-button").get_by_role("button")
        expect(star_button).to_have_text("Star")
        expect(page.get_by_test_id("star-count")).to_have_text("0")

        star_button.click()
        expect(star_button).to_have_text("Starred", timeout=10000)
        expect(page.get_by_test_id("star-count")).to_have_text("1")

        star_button.click()
        expect(star_button).to_have_text("Star", timeout=10000)
        expect(page.get_by_test_id("star-count")).to_have_text("0")

    def test_watch_repository_toggles_and_updates_count(self, app_url: str, page: Page) -> None:
        """Watching increments the count and toggles the button state.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "admin/watchrepo.git")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/admin/watchrepo")

        watch_button = page.get_by_test_id("watch-button").get_by_role("button")
        expect(watch_button).to_have_text("Watch")
        expect(page.get_by_test_id("watch-count")).to_have_text("0")

        watch_button.click()
        expect(watch_button).to_have_text("Unwatch", timeout=10000)
        expect(page.get_by_test_id("watch-count")).to_have_text("1")


class TestFork:
    """Test forking a repository through the UI."""

    def test_fork_creates_empty_repository(self, app_url: str, page: Page) -> None:
        """Forking a repository navigates to the new, empty fork.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        foreign_owner = _create_foreign_owner(app_url)
        _push_repo(app_url, f"{foreign_owner}/forkrepo.git")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/{foreign_owner}/forkrepo")

        page.get_by_test_id("fork-button").click()
        dialog = page.get_by_role("dialog", name="Fork repository")
        expect(dialog).to_be_visible(timeout=10000)

        fork_name = "forkrepo-fork"
        page.get_by_test_id("fork-repo-name").fill(fork_name)
        page.get_by_test_id("fork-repo-submit").click()

        page.wait_for_url(f"{app_url}/{SUPERUSER_USERNAME}/{fork_name}")
        expect(page.get_by_test_id("empty-repository")).to_be_visible(timeout=15000)


class TestBranchesPage:
    """Test the branches and tags page."""

    def test_lists_branches_and_tags(self, app_url: str, page: Page) -> None:
        """The branches page lists branches and tags.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "admin/branchesrepo.git", extra_branches=("develop",), tag="v1.0.0")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/admin/branchesrepo/branches")
        branches = page.get_by_test_id("branches-list")
        expect(branches).to_be_visible(timeout=15000)
        expect(branches).to_contain_text("main")
        expect(branches).to_contain_text("develop")
        expect(branches).to_contain_text("v1.0.0")


class TestReleasesPage:
    """Test the releases page and release creation."""

    def test_create_release(self, app_url: str, page: Page) -> None:
        """Creating a release shows it in the release list.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "admin/releaserepo.git", tag="v1.0.0")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/admin/releaserepo/releases")
        expect(page.get_by_test_id("releases-list")).to_be_visible(timeout=15000)

        page.get_by_test_id("new-release-button").click()
        expect(page.get_by_role("dialog", name="Create release")).to_be_visible(timeout=10000)
        page.get_by_test_id("release-tag-input").fill("v2.0.0")
        page.get_by_test_id("release-name-input").fill("Second release")
        page.get_by_test_id("release-body-input").fill("Release notes for v2.")
        page.get_by_test_id("release-submit").click()

        expect(page.get_by_test_id("release-v2.0.0")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("release-v2.0.0")).to_contain_text("Second release")

    def test_edit_release(self, app_url: str, page: Page) -> None:
        """A release can be edited by its author.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "admin/editreleaserepo.git", tag="v1.0.0")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/admin/editreleaserepo/releases")
        expect(page.get_by_test_id("releases-list")).to_be_visible(timeout=15000)

        page.get_by_test_id("new-release-button").click()
        page.get_by_test_id("release-tag-input").fill("v1.0.0")
        page.get_by_test_id("release-name-input").fill("First release")
        page.get_by_test_id("release-submit").click()
        expect(page.get_by_test_id("release-v1.0.0")).to_be_visible(timeout=15000)

        page.get_by_test_id("edit-release-v1.0.0").click()
        expect(page.get_by_role("dialog", name="Edit release")).to_be_visible(timeout=10000)
        page.get_by_test_id("edit-release-name-input").fill("Renamed release")
        page.get_by_test_id("edit-release-submit").click()

        expect(page.get_by_test_id("release-v1.0.0")).to_contain_text("Renamed release", timeout=15000)


class TestIssueComments:
    """Test issue detail and commenting."""

    def test_create_issue_and_comment(self, app_url: str, page: Page) -> None:
        """Issue descriptions and comments display rendered Markdown after reloading.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "admin/issuecommentrepo.git")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/admin/issuecommentrepo/issues/new")
        page.get_by_test_id("issue-title-input").fill("Commentable issue")
        page.get_by_test_id("issue-body-input").fill("## Issue details\n\nIssue **body**")
        page.get_by_test_id("submit-issue-btn").click()

        page.get_by_test_id("issue-1").get_by_role("link").click()
        expect(page.get_by_test_id("issue-detail")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("issue-state")).to_contain_text("Open")

        page.get_by_test_id("comment-input").fill("This is my **comment** with [a link](https://example.com).")
        page.get_by_test_id("comment-submit").click()

        expect(page.get_by_test_id("comment-input")).to_have_value("", timeout=15000)
        page.reload()

        description = page.get_by_test_id("issue-detail").locator(".markdown-body").first
        expect(description.get_by_role("heading", name="Issue details", level=2)).to_be_visible(timeout=15000)
        expect(description.locator("strong")).to_have_text("body")
        expect(description).not_to_contain_text("## Issue details")
        expect(description).not_to_contain_text("**body**")

        comment = page.get_by_test_id("comments-section").locator(".markdown-body")
        expect(comment).to_have_text("This is my comment with a link.", timeout=15000)
        expect(comment.locator("strong")).to_have_text("comment")
        expect(comment.get_by_role("link", name="a link")).to_have_attribute("href", "https://example.com")
        expect(comment).not_to_contain_text("**comment**")
        expect(comment).not_to_contain_text("[a link]")

    def test_edit_comment(self, app_url: str, page: Page) -> None:
        """A comment can be edited by its author.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "admin/editcommentrepo.git")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/admin/editcommentrepo/issues/new")
        page.get_by_test_id("issue-title-input").fill("Editable issue")
        page.get_by_test_id("submit-issue-btn").click()

        page.get_by_test_id("issue-1").get_by_role("link").click()
        expect(page.get_by_test_id("issue-detail")).to_be_visible(timeout=15000)

        page.get_by_test_id("comment-input").fill("Original comment.")
        page.get_by_test_id("comment-submit").click()
        expect(page.get_by_test_id("comment-input")).to_have_value("", timeout=15000)
        expect(page.get_by_test_id("comments-section")).to_contain_text("Original comment.", timeout=15000)

        page.get_by_test_id("comments-section").get_by_role("button", name="Edit").click()
        page.locator('[data-testid^="edit-comment-input-"]').fill("Edited comment.")
        page.get_by_role("button", name="Save").click()

        # The editor closes only after the update is persisted.
        expect(page.locator('[data-testid^="edit-comment-input-"]')).to_have_count(0, timeout=15000)
        expect(page.get_by_test_id("comments-section")).to_contain_text("Edited comment.", timeout=15000)
        expect(page.get_by_test_id("comments-section")).not_to_contain_text("Original comment.")

    def test_close_issue(self, app_url: str, page: Page) -> None:
        """An issue can be closed from the detail page.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "admin/closeissuerepo.git")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/admin/closeissuerepo/issues/new")
        page.get_by_test_id("issue-title-input").fill("Close me")
        page.get_by_test_id("submit-issue-btn").click()

        page.get_by_test_id("issue-1").get_by_role("link").click()
        expect(page.get_by_test_id("issue-detail")).to_be_visible(timeout=15000)

        page.get_by_test_id("toggle-issue-state").click()
        expect(page.get_by_test_id("issue-state")).to_contain_text("Closed", timeout=15000)

    def test_edit_issue(self, app_url: str, page: Page) -> None:
        """An issue's title and body can be edited by its author.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "admin/editissuerepo.git")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/admin/editissuerepo/issues/new")
        page.get_by_test_id("issue-title-input").fill("Original title")
        page.get_by_test_id("issue-body-input").fill("Original body")
        page.get_by_test_id("submit-issue-btn").click()

        page.get_by_test_id("issue-1").get_by_role("link").click()
        expect(page.get_by_test_id("issue-detail")).to_be_visible(timeout=15000)

        page.get_by_test_id("edit-issue").click()
        page.get_by_test_id("edit-issue-title").fill("Updated title")
        page.get_by_test_id("edit-issue-body").fill("Updated body")
        page.get_by_test_id("edit-issue-submit").click()

        expect(page.get_by_test_id("issue-detail")).to_contain_text("Updated title", timeout=15000)
        expect(page.get_by_test_id("issue-detail")).to_contain_text("Updated body", timeout=15000)
        expect(page.get_by_test_id("issue-detail")).not_to_contain_text("Original title")

    def test_delete_comment(self, app_url: str, page: Page) -> None:
        """A comment can be deleted by its author.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "admin/deletecommentrepo.git")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/admin/deletecommentrepo/issues/new")
        page.get_by_test_id("issue-title-input").fill("Delete comment issue")
        page.get_by_test_id("submit-issue-btn").click()

        page.get_by_test_id("issue-1").get_by_role("link").click()
        expect(page.get_by_test_id("issue-detail")).to_be_visible(timeout=15000)

        page.get_by_test_id("comment-input").fill("Delete me.")
        page.get_by_test_id("comment-submit").click()
        expect(page.get_by_test_id("comment-input")).to_have_value("", timeout=15000)
        expect(page.get_by_test_id("comments-section")).to_contain_text("Delete me.", timeout=15000)

        page.once("dialog", lambda dialog: dialog.accept())
        page.locator('[data-testid^="delete-comment-"]').click()

        expect(page.get_by_test_id("comments-section")).not_to_contain_text("Delete me.", timeout=15000)


class TestPullRequestCommentsAndMerge:
    """Test pull request detail, commenting and merging."""

    def test_comment_and_merge_pull_request(self, app_url: str, page: Page) -> None:
        """PR descriptions and comments render Markdown, and the PR can be merged.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "admin/prmergerepo.git", extra_branches=("feature",))
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/admin/prmergerepo/pulls/new")
        page.wait_for_selector('[data-testid="pr-source-branch"] option[value="feature"]', state="attached")
        page.get_by_test_id("pr-source-branch").select_option("feature")
        page.get_by_test_id("pr-title-input").fill("Merge the feature")
        page.get_by_test_id("pr-body-input").fill("## PR details\n\nPR **body**")
        page.get_by_test_id("submit-pr-btn").click()

        page.get_by_test_id("pr-1").get_by_role("link").click()
        expect(page.get_by_test_id("pull-detail")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("pr-state")).to_contain_text("Open")

        page.get_by_test_id("comment-input").fill("Looks **good** to me.")
        page.get_by_test_id("comment-submit").click()

        expect(page.get_by_test_id("comment-input")).to_have_value("", timeout=15000)
        page.reload()

        description = page.get_by_test_id("pull-detail").locator(".markdown-body").first
        expect(description.get_by_role("heading", name="PR details", level=2)).to_be_visible(timeout=15000)
        expect(description.locator("strong")).to_have_text("body")
        expect(description).not_to_contain_text("## PR details")
        expect(description).not_to_contain_text("**body**")

        comment = page.get_by_test_id("comments-section").locator(".markdown-body")
        expect(comment).to_have_text("Looks good to me.", timeout=15000)
        expect(comment.locator("strong")).to_have_text("good")
        expect(comment).not_to_contain_text("**good**")

        page.get_by_test_id("merge-pr").click()
        expect(page.get_by_test_id("pr-state")).to_contain_text("Merged", timeout=15000)

    def test_edit_pull_request(self, app_url: str, page: Page) -> None:
        """A pull request's title and body can be edited by its author.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "admin/editprrepo.git", extra_branches=("feature",))
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/admin/editprrepo/pulls/new")
        page.wait_for_selector('[data-testid="pr-source-branch"] option[value="feature"]', state="attached")
        page.get_by_test_id("pr-source-branch").select_option("feature")
        page.get_by_test_id("pr-title-input").fill("Original PR")
        page.get_by_test_id("submit-pr-btn").click()

        page.get_by_test_id("pr-1").get_by_role("link").click()
        expect(page.get_by_test_id("pull-detail")).to_be_visible(timeout=15000)

        page.get_by_test_id("edit-pr").click()
        page.get_by_test_id("edit-pr-title").fill("Updated PR")
        page.get_by_test_id("edit-pr-body").fill("Updated PR body")
        page.get_by_test_id("edit-pr-submit").click()

        expect(page.get_by_test_id("pull-detail")).to_contain_text("Updated PR", timeout=15000)
        expect(page.get_by_test_id("pull-detail")).to_contain_text("Updated PR body", timeout=15000)


class TestActivityAndFeed:
    """Test the repository activity page and the dashboard feed."""

    def test_activity_statistics_and_dashboard_star_feed(self, app_url: str, page: Page) -> None:
        """Show pushed Git data in analytics and star events in the dashboard.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "admin/activityrepo.git")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/admin/activityrepo")
        page.get_by_test_id("star-button").get_by_role("button").click()
        expect(page.get_by_test_id("star-count")).to_have_text("1", timeout=10000)

        page.goto(f"{app_url}/admin/activityrepo/activity")
        expect(page.get_by_role("combobox", name="Activity period")).to_be_visible(timeout=15000)
        expect(page.get_by_role("main")).to_contain_text("4 additions and 0 deletions")
        period = page.get_by_role("combobox", name="Activity period")
        expect(period.locator("option")).to_have_text(
            ["1 day", "3 days", "1 week", "1 month", "3 months", "6 months", "1 year"]
        )
        for days in [1, 3, 30, 90, 180, 365]:
            with page.expect_response(
                lambda response, days=days: response.url.endswith(f"/activity/statistics?days={days}")
            ) as statistics:
                period.select_option(str(days))
            assert statistics.value.status == 200
            assert len(statistics.value.json()["daily_commits"]) == days + 1
            expect(page.get_by_role("main")).to_contain_text("4 additions and 0 deletions")

        page.get_by_role("button", name="Contributors", exact=True).click()
        contributor = page.get_by_test_id("activity-contributor")
        expect(contributor).to_contain_text("Test User")
        expect(contributor).to_contain_text("1 Commits 4++ 0--")
        page.get_by_role("combobox", name="Contribution metric").select_option("additions")
        expect(page.get_by_role("group", name="Overall additions", exact=True)).to_be_visible()

        page.get_by_role("button", name="Code frequency", exact=True).click()
        expect(page.get_by_role("group", name="Weekly additions and deletions", exact=True)).to_be_visible()

        page.get_by_role("button", name="Recent commits", exact=True).click()
        page.get_by_role("link", name="Initial commit", exact=True).click()
        expect(page.get_by_test_id("commit-detail")).to_be_visible(timeout=15000)

        page.goto(f"{app_url}/")
        expect(page.get_by_test_id("dashboard-feed")).to_contain_text("admin/activityrepo", timeout=15000)
        expect(page.get_by_test_id("dashboard-feed")).to_contain_text("star")


class TestSocialListings:
    """Test stargazers, watchers and forks listings."""

    def test_stargazers_and_watchers(self, app_url: str, page: Page) -> None:
        """Stargazers and watchers pages list the acting user.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "admin/peoplelistrepo.git")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/admin/peoplelistrepo")
        page.get_by_test_id("star-button").get_by_role("button").click()
        page.get_by_test_id("watch-button").get_by_role("button").click()
        expect(page.get_by_test_id("star-count")).to_have_text("1", timeout=10000)
        expect(page.get_by_test_id("watch-count")).to_have_text("1")

        page.goto(f"{app_url}/admin/peoplelistrepo/stars")
        expect(page.get_by_test_id("people-list")).to_contain_text("Admin User", timeout=15000)

        page.goto(f"{app_url}/admin/peoplelistrepo/watchers")
        expect(page.get_by_test_id("people-list")).to_contain_text("Admin User", timeout=15000)

    def test_forks_listing(self, app_url: str, page: Page) -> None:
        """The forks page lists a created fork.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        foreign_owner = _create_foreign_owner(app_url)
        _push_repo(app_url, f"{foreign_owner}/forkslistrepo.git")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/{foreign_owner}/forkslistrepo")
        page.get_by_test_id("fork-button").click()
        page.get_by_test_id("fork-repo-name").fill("forkslistrepo-fork")
        page.get_by_test_id("fork-repo-submit").click()
        page.wait_for_url(f"{app_url}/{SUPERUSER_USERNAME}/forkslistrepo-fork")

        page.goto(f"{app_url}/{foreign_owner}/forkslistrepo/forks")
        expect(page.get_by_test_id("forks-list")).to_contain_text("forkslistrepo-fork", timeout=15000)


class TestExplore:
    """Test the explore page."""

    def test_explore_lists_and_filters_repositories(self, app_url: str, page: Page) -> None:
        """Explore lists repositories and filters by the search box.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "admin/explorerepo.git")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/explore")
        expect(page.get_by_test_id("explore-repositories")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("explore-repo-explorerepo")).to_be_visible()

        page.get_by_test_id("explore-search").fill("no-such-repository")
        expect(page.get_by_test_id("explore-repo-explorerepo")).to_have_count(0)


class TestProfile:
    """Test the user profile page."""

    def test_profile_repositories_and_starred(self, app_url: str, page: Page) -> None:
        """The profile lists owned and starred repositories.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "admin/profilerepo.git")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/admin/profilerepo")
        page.get_by_test_id("star-button").get_by_role("button").click()
        expect(page.get_by_test_id("star-count")).to_have_text("1", timeout=10000)

        page.goto(f"{app_url}/profile/{SUPERUSER_USERNAME}")
        expect(page.get_by_test_id("user-profile")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("profile-tab-repositories")).to_contain_text("Repositories")
        expect(page.get_by_test_id("profile-repo-profilerepo")).to_be_visible()

        page.get_by_test_id("profile-tab-starred").click()
        expect(page.get_by_test_id("profile-repo-profilerepo")).to_be_visible(timeout=15000)


class TestEmptyRepository:
    """Test the empty repository state."""

    def test_newly_created_repository_shows_empty_state(self, app_url: str, page: Page) -> None:
        """A repository created via the UI shows the empty state.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/repositories")
        page.get_by_test_id("create-repository-button").click()
        expect(page.get_by_role("dialog", name="Create Repository")).to_be_visible(timeout=10000)
        page.get_by_test_id("create-repo-owner").fill("admin")
        page.get_by_test_id("create-repo-name").fill("emptyrepo")
        page.get_by_test_id("create-repo-submit").click()

        page.goto(f"{app_url}/admin/emptyrepo")
        expect(page.get_by_test_id("empty-repository")).to_be_visible(timeout=15000)

    def test_repository_without_stored_data_shows_empty_state(self, app_url: str, page: Page) -> None:
        """A repository row without stored Git data still loads as empty.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        create_repository_row("admin", "orphanrepo")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/admin/orphanrepo")
        expect(page.get_by_test_id("empty-repository")).to_be_visible(timeout=15000)
