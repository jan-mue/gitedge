"""End-to-end tests for the social and forge features.

Covers the functionality ported from the Gitea-like UI: starring, watching,
forking, branches and tags, releases, issue comments, pull request comments
and merging, the activity feed, stargazers/watchers/forks listings, explore,
user profiles, and empty repositories.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from playwright.sync_api import expect

from tests.integration.conftest import FIRST_SUPERUSER, FIRST_SUPERUSER_PASSWORD, log_in_user

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
    remote_url = f"{app_url}/api/v1/{repo_name}"

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


class TestStarAndWatch:
    """Test the star and watch repository buttons."""

    def test_star_repository_toggles_and_updates_count(self, app_url: str, page: Page) -> None:
        """Starring increments the count and toggles the button state.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "social/starrepo.git")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/social/starrepo")

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
        _push_repo(app_url, "social/watchrepo.git")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/social/watchrepo")

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
        _push_repo(app_url, "social/forkrepo.git")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/social/forkrepo")

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
        _push_repo(app_url, "social/branchesrepo.git", extra_branches=("develop",), tag="v1.0.0")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/social/branchesrepo/branches")
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
        _push_repo(app_url, "social/releaserepo.git", tag="v1.0.0")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/social/releaserepo/releases")
        expect(page.get_by_test_id("releases-list")).to_be_visible(timeout=15000)

        page.get_by_test_id("new-release-button").click()
        expect(page.get_by_role("dialog", name="Create release")).to_be_visible(timeout=10000)
        page.get_by_test_id("release-tag-input").fill("v2.0.0")
        page.get_by_test_id("release-name-input").fill("Second release")
        page.get_by_test_id("release-body-input").fill("Release notes for v2.")
        page.get_by_test_id("release-submit").click()

        expect(page.get_by_test_id("release-v2.0.0")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("release-v2.0.0")).to_contain_text("Second release")


class TestIssueComments:
    """Test issue detail and commenting."""

    def test_create_issue_and_comment(self, app_url: str, page: Page) -> None:
        """A comment can be added to an issue and is shown in the timeline.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "social/issuecommentrepo.git")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/social/issuecommentrepo/issues/new")
        page.get_by_test_id("issue-title-input").fill("Commentable issue")
        page.get_by_test_id("issue-body-input").fill("Issue body")
        page.get_by_test_id("submit-issue-btn").click()

        page.get_by_test_id("issue-1").get_by_role("link").click()
        expect(page.get_by_test_id("issue-detail")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("issue-state")).to_contain_text("Open")

        page.get_by_test_id("comment-input").fill("This is my comment.")
        page.get_by_test_id("comment-submit").click()

        expect(page.get_by_test_id("comments-section")).to_contain_text("This is my comment.", timeout=15000)

    def test_close_issue(self, app_url: str, page: Page) -> None:
        """An issue can be closed from the detail page.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "social/closeissuerepo.git")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/social/closeissuerepo/issues/new")
        page.get_by_test_id("issue-title-input").fill("Close me")
        page.get_by_test_id("submit-issue-btn").click()

        page.get_by_test_id("issue-1").get_by_role("link").click()
        expect(page.get_by_test_id("issue-detail")).to_be_visible(timeout=15000)

        page.get_by_test_id("toggle-issue-state").click()
        expect(page.get_by_test_id("issue-state")).to_contain_text("Closed", timeout=15000)


class TestPullRequestCommentsAndMerge:
    """Test pull request detail, commenting and merging."""

    def test_comment_and_merge_pull_request(self, app_url: str, page: Page) -> None:
        """A pull request can be commented on and merged.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "social/prmergerepo.git", extra_branches=("feature",))
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/social/prmergerepo/pulls/new")
        page.wait_for_selector('[data-testid="pr-source-branch"] option[value="feature"]', state="attached")
        page.get_by_test_id("pr-source-branch").select_option("feature")
        page.get_by_test_id("pr-title-input").fill("Merge the feature")
        page.get_by_test_id("pr-body-input").fill("PR body")
        page.get_by_test_id("submit-pr-btn").click()

        page.get_by_test_id("pr-1").get_by_role("link").click()
        expect(page.get_by_test_id("pull-detail")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("pr-state")).to_contain_text("Open")

        page.get_by_test_id("comment-input").fill("Looks good to me.")
        page.get_by_test_id("comment-submit").click()
        expect(page.get_by_test_id("comments-section")).to_contain_text("Looks good to me.", timeout=15000)

        page.get_by_test_id("merge-pr").click()
        expect(page.get_by_test_id("pr-state")).to_contain_text("Merged", timeout=15000)


class TestActivityAndFeed:
    """Test the repository activity page and the dashboard feed."""

    def test_activity_and_feed_show_star_event(self, app_url: str, page: Page) -> None:
        """Starring a repository records activity visible in both feeds.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "social/activityrepo.git")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/social/activityrepo")
        page.get_by_test_id("star-button").get_by_role("button").click()
        expect(page.get_by_test_id("star-count")).to_have_text("1", timeout=10000)

        page.goto(f"{app_url}/social/activityrepo/activity")
        expect(page.get_by_test_id("activity-list")).to_contain_text("star", timeout=15000)

        page.goto(f"{app_url}/")
        expect(page.get_by_test_id("dashboard-feed")).to_contain_text("social/activityrepo", timeout=15000)


class TestSocialListings:
    """Test stargazers, watchers and forks listings."""

    def test_stargazers_and_watchers(self, app_url: str, page: Page) -> None:
        """Stargazers and watchers pages list the acting user.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "social/peoplelistrepo.git")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/social/peoplelistrepo")
        page.get_by_test_id("star-button").get_by_role("button").click()
        page.get_by_test_id("watch-button").get_by_role("button").click()
        expect(page.get_by_test_id("star-count")).to_have_text("1", timeout=10000)
        expect(page.get_by_test_id("watch-count")).to_have_text("1")

        page.goto(f"{app_url}/social/peoplelistrepo/stars")
        expect(page.get_by_test_id("people-list")).to_contain_text("Admin User", timeout=15000)

        page.goto(f"{app_url}/social/peoplelistrepo/watchers")
        expect(page.get_by_test_id("people-list")).to_contain_text("Admin User", timeout=15000)

    def test_forks_listing(self, app_url: str, page: Page) -> None:
        """The forks page lists a created fork.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "social/forkslistrepo.git")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/social/forkslistrepo")
        page.get_by_test_id("fork-button").click()
        page.get_by_test_id("fork-repo-name").fill("forkslistrepo-fork")
        page.get_by_test_id("fork-repo-submit").click()
        page.wait_for_url(f"{app_url}/{SUPERUSER_USERNAME}/forkslistrepo-fork")

        page.goto(f"{app_url}/social/forkslistrepo/forks")
        expect(page.get_by_test_id("forks-list")).to_contain_text("forkslistrepo-fork", timeout=15000)


class TestExplore:
    """Test the explore page."""

    def test_explore_lists_and_filters_repositories(self, app_url: str, page: Page) -> None:
        """Explore lists repositories and filters by the search box.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo(app_url, "social/explorerepo.git")
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
        _push_repo(app_url, "social/profilerepo.git")
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/social/profilerepo")
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
        page.get_by_test_id("create-repo-owner").fill("emptyuser")
        page.get_by_test_id("create-repo-name").fill("emptyrepo")
        page.get_by_test_id("create-repo-submit").click()

        page.goto(f"{app_url}/emptyuser/emptyrepo")
        expect(page.get_by_test_id("empty-repository")).to_be_visible(timeout=15000)
