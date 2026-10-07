"""Integration tests for repository commit history and commit detail."""

from __future__ import annotations

import re
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


def _run_git(cwd: Path, args: list[str]) -> str:
    """Run a git command and return its output.

    Args:
        cwd: Working directory for the command.
        args: Git command arguments.

    Returns:
        Command stdout as string.
    """
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _push_repo_with_commits(app_url: str, repo_name: str, count: int = 3) -> None:
    """Push a repository with multiple commits.

    Args:
        app_url: Base URL of the GitEdge frontend.
        repo_name: Repository path (e.g. "admin/repo.git").
        count: Total number of commits to create.
    """
    remote_url = f"{app_url}/api/v1/{repo_name}"

    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = Path(tmpdir) / "source"
        source_dir.mkdir()

        _run_git(source_dir, ["init", "-b", "main"])
        _run_git(source_dir, ["config", "user.email", "test@example.com"])
        _run_git(source_dir, ["config", "user.name", "Test User"])

        (source_dir / "README.md").write_text("# Commit Test\n\nA repository for commit tests.\n")
        _run_git(source_dir, ["add", "."])
        _run_git(source_dir, ["commit", "-m", "Initial commit"])

        for i in range(2, count + 1):
            src_dir = source_dir / "src"
            src_dir.mkdir(exist_ok=True)
            (src_dir / f"file{i}.txt").write_text(f"content {i}\n")
            _run_git(source_dir, ["add", "."])
            _run_git(source_dir, ["commit", "-m", f"Commit number {i}"])

        _run_git(source_dir, ["remote", "add", "origin", remote_url])
        _run_git(source_dir, ["push", "-u", "--force", "origin", "main"])


class TestCommitHistory:
    """Test the commit history and commit detail pages."""

    def test_commits_list_and_detail(self, app_url: str, page: Page) -> None:
        """The commits list shows history and links to commit detail.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo_with_commits(app_url, "admin/historyrepo.git", count=3)
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/admin/historyrepo/commits/branch/main")
        commits = page.get_by_test_id("commits-list")
        expect(commits).to_be_visible(timeout=15000)
        expect(commits).to_contain_text("Initial commit")
        expect(commits).to_contain_text("Commit number 3")

        commits.get_by_role("link", name="Commit number 3").click()
        expect(page.get_by_test_id("commit-detail")).to_be_visible(timeout=15000)
        expect(page).to_have_url(re.compile(r"/admin/historyrepo/commit/[0-9a-f]+$"))
        expect(page.get_by_test_id("commit-detail")).to_contain_text("changed")
        expect(page.get_by_test_id("commit-detail")).to_contain_text("src/file3.txt")

    def test_last_commit_sha_links_to_commit_detail(self, app_url: str, page: Page) -> None:
        """The code page's last-commit SHA links to the commit detail page.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_repo_with_commits(app_url, "admin/shalinkrepo.git", count=2)
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/admin/shalinkrepo")
        expect(page.get_by_test_id("file-tree")).to_be_visible(timeout=15000)

        page.get_by_test_id("last-commit-sha").click()
        expect(page.get_by_test_id("commit-detail")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("commit-detail")).to_contain_text("Commit number 2")

    def test_commits_page_with_no_history(self, app_url: str, page: Page) -> None:
        """An empty repository shows an empty commit history.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/repositories")
        page.get_by_test_id("create-repository-button").click()
        page.get_by_test_id("create-repo-owner").fill("admin")
        page.get_by_test_id("create-repo-name").fill("emptycommits")
        page.get_by_test_id("create-repo-submit").click()

        page.goto(f"{app_url}/admin/emptycommits/commits")
        expect(page.get_by_test_id("commits-list")).to_contain_text("No commits yet", timeout=15000)
