"""Integration tests for repository UI components.

Tests cover: RepoHeader tabs, ReadmeViewer, branch switcher,
issues page, pull requests page, and new issue/PR forms.
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


def _run_git(cwd: Path, args: list[str]) -> str:
    """Run a git command and return its output.

    Args:
        cwd: Working directory for the command.
        args: Git command arguments.

    Returns:
        Command stdout as string.
    """
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Git failed: {e.cmd}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        raise


def _push_test_repo(app_url: str, repo_name: str) -> None:
    """Push a test repository with known files to the server.

    Creates a repo with:
    - README.md (markdown file with heading and paragraphs)
    - src/ (directory)
    - src/main.py (Python file)

    Args:
        app_url: Base URL of the GitEdge frontend.
        repo_name: Repository name (e.g., "testuser/test.git").
    """
    remote_url = f"{app_url}/api/v1/{repo_name}"

    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = Path(tmpdir) / "source"
        source_dir.mkdir()

        _run_git(source_dir, ["init", "-b", "main"])
        _run_git(source_dir, ["config", "user.email", "test@example.com"])
        _run_git(source_dir, ["config", "user.name", "Test User"])

        # Create files
        readme = source_dir / "README.md"
        readme.write_text(
            "# Test Repository\n\nThis is a test repository for UI testing.\n\n"
            "It contains sample files for integration tests.\n"
        )

        src_dir = source_dir / "src"
        src_dir.mkdir()

        main_py = src_dir / "main.py"
        main_py.write_text('def main():\n    print("Hello, World!")\n\n\nif __name__ == "__main__":\n    main()\n')

        _run_git(source_dir, ["add", "."])
        _run_git(source_dir, ["commit", "-m", "Initial commit"])
        _run_git(source_dir, ["remote", "add", "origin", remote_url])
        _run_git(source_dir, ["push", "-u", "--force", "origin", "main"])


def _push_multi_branch_repo(app_url: str, repo_name: str) -> None:
    """Push a test repository with multiple branches.

    Creates a repo with branches: main, develop, feature/login.

    Args:
        app_url: Base URL of the GitEdge frontend.
        repo_name: Repository name (e.g., "testuser/multibranch.git").
    """
    remote_url = f"{app_url}/api/v1/{repo_name}"

    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = Path(tmpdir) / "source"
        source_dir.mkdir()

        _run_git(source_dir, ["init", "-b", "main"])
        _run_git(source_dir, ["config", "user.email", "test@example.com"])
        _run_git(source_dir, ["config", "user.name", "Test User"])

        # Create initial commit on main
        readme = source_dir / "README.md"
        readme.write_text("# Multi-Branch Repo\n\nMain branch content.\n")

        _run_git(source_dir, ["add", "."])
        _run_git(source_dir, ["commit", "-m", "Initial commit on main"])

        # Create develop branch with different content
        _run_git(source_dir, ["checkout", "-b", "develop"])
        readme.write_text("# Multi-Branch Repo\n\nDevelop branch content.\n")
        dev_file = source_dir / "dev.txt"
        dev_file.write_text("development file\n")
        _run_git(source_dir, ["add", "."])
        _run_git(source_dir, ["commit", "-m", "Add develop content"])

        # Create feature/login branch
        _run_git(source_dir, ["checkout", "main"])
        _run_git(source_dir, ["checkout", "-b", "feature/login"])
        login_file = source_dir / "login.txt"
        login_file.write_text("login feature\n")
        _run_git(source_dir, ["add", "."])
        _run_git(source_dir, ["commit", "-m", "Add login feature"])

        # Push all branches
        _run_git(source_dir, ["remote", "add", "origin", remote_url])
        _run_git(source_dir, ["push", "-u", "--force", "origin", "main"])
        _run_git(source_dir, ["push", "-u", "--force", "origin", "develop"])
        _run_git(source_dir, ["push", "-u", "--force", "origin", "feature/login"])


class TestReadmeViewer:
    """Test the README viewer component."""

    def test_readme_renders_with_markdown(self, app_url: str, page: Page) -> None:
        """Test that README renders with markdown-body class and HTML content.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_test_repo(app_url, "uitest/readmerepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/uitest/readmerepo")

        # Wait for file tree to load first
        expect(page.get_by_test_id("file-tree")).to_be_visible(timeout=15000)

        # Verify README viewer is shown
        readme_viewer = page.get_by_test_id("readme-viewer")
        expect(readme_viewer).to_be_visible(timeout=10000)

        # Verify readme content container
        readme_content = page.get_by_test_id("readme-content")
        expect(readme_content).to_be_visible()

        # Verify markdown-body class is applied
        markdown_body = readme_viewer.locator(".markdown-body")
        expect(markdown_body).to_be_visible()

        # Verify rendered HTML contains heading
        expect(markdown_body.locator("h1")).to_contain_text("Test Repository")


class TestRepoHeader:
    """Test the repository header tab navigation."""

    def test_tabs_are_visible(self, app_url: str, page: Page) -> None:
        """Test that all tabs are visible in the repo header.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_test_repo(app_url, "uitest/tabrepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/uitest/tabrepo")

        expect(page.get_by_test_id("file-tree")).to_be_visible(timeout=15000)

        # Verify repo header and tabs
        expect(page.get_by_test_id("repo-header")).to_be_visible()
        expect(page.get_by_test_id("tab-code")).to_be_visible()
        expect(page.get_by_test_id("tab-issues")).to_be_visible()
        expect(page.get_by_test_id("tab-pulls")).to_be_visible()

    def test_navigate_to_issues_tab(self, app_url: str, page: Page) -> None:
        """Test clicking Issues tab navigates to issues page.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_test_repo(app_url, "uitest/issuetabrepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/uitest/issuetabrepo")

        expect(page.get_by_test_id("file-tree")).to_be_visible(timeout=15000)

        # Click Issues tab
        page.get_by_test_id("tab-issues").click()

        # Verify issues page loads with empty state
        expect(page.get_by_test_id("issues-empty-state")).to_be_visible(timeout=10000)

    def test_navigate_to_pulls_tab(self, app_url: str, page: Page) -> None:
        """Test clicking Pull Requests tab navigates to pulls page.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_test_repo(app_url, "uitest/pulltabrepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/uitest/pulltabrepo")

        expect(page.get_by_test_id("file-tree")).to_be_visible(timeout=15000)

        # Click Pull Requests tab
        page.get_by_test_id("tab-pulls").click()

        # Verify pulls page loads with empty state
        expect(page.get_by_test_id("pulls-empty-state")).to_be_visible(timeout=10000)

    def test_navigate_back_to_code_tab(self, app_url: str, page: Page) -> None:
        """Test navigating from Issues back to Code tab.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_test_repo(app_url, "uitest/codetabrepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/uitest/codetabrepo")

        expect(page.get_by_test_id("file-tree")).to_be_visible(timeout=15000)

        # Go to Issues
        page.get_by_test_id("tab-issues").click()
        expect(page.get_by_test_id("issues-empty-state")).to_be_visible(timeout=10000)

        # Go back to Code
        page.get_by_test_id("tab-code").click()
        expect(page.get_by_test_id("file-tree")).to_be_visible(timeout=10000)

    def test_theme_toggle(self, app_url: str, page: Page) -> None:
        """Test that the theme toggle button is present and clickable.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_test_repo(app_url, "uitest/themerepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/uitest/themerepo")

        expect(page.get_by_test_id("file-tree")).to_be_visible(timeout=15000)

        # Verify theme toggle is visible and clickable
        theme_toggle = page.get_by_test_id("theme-toggle")
        expect(theme_toggle).to_be_visible()
        theme_toggle.click()


class TestBranchSwitcher:
    """Test the branch selector dropdown."""

    def test_branch_selector_opens_dropdown(self, app_url: str, page: Page) -> None:
        """Test that clicking branch selector opens the dropdown.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_multi_branch_repo(app_url, "uitest/branchrepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/uitest/branchrepo")

        expect(page.get_by_test_id("file-tree")).to_be_visible(timeout=15000)

        # Click branch selector
        branch_selector = page.get_by_test_id("branch-selector")
        expect(branch_selector).to_be_visible()
        branch_selector.click()

        # Verify dropdown appears with branches
        dropdown = page.get_by_test_id("branch-dropdown")
        expect(dropdown).to_be_visible(timeout=5000)

        # Verify branches are listed
        expect(page.get_by_test_id("branch-option-main")).to_be_visible()
        expect(page.get_by_test_id("branch-option-develop")).to_be_visible()

    def test_switch_branch_updates_tree(self, app_url: str, page: Page) -> None:
        """Test that selecting a different branch updates the file tree.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_multi_branch_repo(app_url, "uitest/switchrepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/uitest/switchrepo")

        expect(page.get_by_test_id("file-tree")).to_be_visible(timeout=15000)

        # Verify we're on main (no dev.txt file)
        expect(page.get_by_test_id("tree-entry-README.md")).to_be_visible()

        # Switch to develop branch
        page.get_by_test_id("branch-selector").click()
        expect(page.get_by_test_id("branch-dropdown")).to_be_visible(timeout=5000)
        page.get_by_test_id("branch-option-develop").click()

        # Verify tree updates - develop branch has dev.txt
        expect(page.get_by_test_id("tree-entry-dev.txt")).to_be_visible(timeout=15000)


class TestIssuesPage:
    """Test the issues page."""

    def test_issues_empty_state(self, app_url: str, page: Page) -> None:
        """Test that the issues page shows empty state.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_test_repo(app_url, "uitest/issuesrepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/uitest/issuesrepo/issues")

        expect(page.get_by_test_id("issues-empty-state")).to_be_visible(timeout=15000)

    def test_new_issue_button_navigates(self, app_url: str, page: Page) -> None:
        """Test that the New Issue button navigates to the create form.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_test_repo(app_url, "uitest/newissuerepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/uitest/newissuerepo/issues")

        expect(page.get_by_test_id("issues-empty-state")).to_be_visible(timeout=15000)

        # Click "New issue" button
        new_issue_btn = page.get_by_test_id("new-issue-btn")
        expect(new_issue_btn).to_be_visible()
        new_issue_btn.click()

        # Verify navigates to new issue form
        expect(page.get_by_test_id("issue-title-input")).to_be_visible(timeout=10000)
        expect(page.get_by_test_id("issue-body-input")).to_be_visible()
        expect(page.get_by_test_id("submit-issue-btn")).to_be_visible()


class TestPullRequestsPage:
    """Test the pull requests page."""

    def test_pulls_empty_state(self, app_url: str, page: Page) -> None:
        """Test that the pull requests page shows empty state.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_test_repo(app_url, "uitest/pullsrepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/uitest/pullsrepo/pulls")

        expect(page.get_by_test_id("pulls-empty-state")).to_be_visible(timeout=15000)

    def test_new_pr_button_navigates(self, app_url: str, page: Page) -> None:
        """Test that the New Pull Request button navigates to the create form.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_test_repo(app_url, "uitest/newprrepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/uitest/newprrepo/pulls")

        expect(page.get_by_test_id("pulls-empty-state")).to_be_visible(timeout=15000)

        # Click "New pull request" button
        new_pr_btn = page.get_by_test_id("new-pr-btn")
        expect(new_pr_btn).to_be_visible()
        new_pr_btn.click()

        # Verify navigates to new PR form
        expect(page.get_by_test_id("pr-title-input")).to_be_visible(timeout=10000)
        expect(page.get_by_test_id("pr-body-input")).to_be_visible()
        expect(page.get_by_test_id("submit-pr-btn")).to_be_visible()


class TestNewIssueForm:
    """Test the new issue creation form."""

    def test_form_elements_present(self, app_url: str, page: Page) -> None:
        """Test that all form elements are present on the new issue page.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_test_repo(app_url, "uitest/issueformrepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/uitest/issueformrepo/issues/new")

        # Verify form elements
        title_input = page.get_by_test_id("issue-title-input")
        expect(title_input).to_be_visible(timeout=15000)

        body_input = page.get_by_test_id("issue-body-input")
        expect(body_input).to_be_visible()

        submit_btn = page.get_by_test_id("submit-issue-btn")
        expect(submit_btn).to_be_visible()

        # Fill in the form to verify interactivity
        title_input.fill("Test issue title")
        body_input.fill("This is a test issue description.")

        expect(title_input).to_have_value("Test issue title")
        expect(body_input).to_have_value("This is a test issue description.")


class TestNewPRForm:
    """Test the new pull request creation form."""

    def test_form_elements_present(self, app_url: str, page: Page) -> None:
        """Test that all form elements are present on the new PR page.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_test_repo(app_url, "uitest/prformrepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/uitest/prformrepo/pulls/new")

        # Verify form elements
        title_input = page.get_by_test_id("pr-title-input")
        expect(title_input).to_be_visible(timeout=15000)

        body_input = page.get_by_test_id("pr-body-input")
        expect(body_input).to_be_visible()

        submit_btn = page.get_by_test_id("submit-pr-btn")
        expect(submit_btn).to_be_visible()

        # Fill in the form to verify interactivity
        title_input.fill("Test PR title")
        body_input.fill("This is a test PR description.")

        expect(title_input).to_have_value("Test PR title")
        expect(body_input).to_have_value("This is a test PR description.")


class TestCreateIssue:
    """Test creating an issue through the UI."""

    def test_create_issue(self, app_url: str, page: Page) -> None:
        """Test that a new issue can be created and appears in the list.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_test_repo(app_url, "uitest/createissuerepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/uitest/createissuerepo/issues/new")

        page.get_by_test_id("issue-title-input").fill("My first issue")
        page.get_by_test_id("issue-body-input").fill("This is the issue body.")
        page.get_by_test_id("submit-issue-btn").click()

        expect(page.get_by_test_id("issue-1")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("issue-1")).to_contain_text("My first issue")


class TestCreatePullRequest:
    """Test creating a pull request through the UI."""

    def test_create_pull_request(self, app_url: str, page: Page) -> None:
        """Test that a new pull request can be created and appears in the list.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_test_repo(app_url, "uitest/createprrepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/uitest/createprrepo/pulls/new")

        page.wait_for_selector(
            '[data-testid="pr-source-branch"] option[value="main"]',
            state="attached",
        )
        page.get_by_test_id("pr-source-branch").select_option("main")
        page.get_by_test_id("pr-title-input").fill("My first pull request")
        page.get_by_test_id("pr-body-input").fill("This is the PR body.")
        page.get_by_test_id("submit-pr-btn").click()

        expect(page.get_by_test_id("pr-1")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("pr-1")).to_contain_text("My first pull request")


class TestIssuesAndPullRequests:
    """Test interactions between issues and pull requests."""

    def test_issues_and_pull_requests_share_numbering(self, app_url: str, page: Page) -> None:
        """Issues and pull requests share a number sequence and stay separate.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_test_repo(app_url, "uitest/mixedrepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/uitest/mixedrepo/issues/new")
        page.get_by_test_id("issue-title-input").fill("Issue one")
        page.get_by_test_id("issue-body-input").fill("Issue body")
        page.get_by_test_id("submit-issue-btn").click()
        expect(page.get_by_test_id("issue-1")).to_be_visible(timeout=15000)

        page.goto(f"{app_url}/uitest/mixedrepo/pulls/new")
        page.wait_for_selector(
            '[data-testid="pr-source-branch"] option[value="main"]',
            state="attached",
        )
        page.get_by_test_id("pr-source-branch").select_option("main")
        page.get_by_test_id("pr-title-input").fill("Pull request two")
        page.get_by_test_id("pr-body-input").fill("Pull request body")
        page.get_by_test_id("submit-pr-btn").click()
        expect(page.get_by_test_id("pr-2")).to_be_visible(timeout=15000)

        # The issues list must not contain the pull request.
        page.goto(f"{app_url}/uitest/mixedrepo/issues")
        expect(page.get_by_test_id("issue-1")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("issue-2")).to_have_count(0)

        # The pull requests list shows the pull request.
        page.goto(f"{app_url}/uitest/mixedrepo/pulls")
        expect(page.get_by_test_id("pr-2")).to_be_visible(timeout=15000)


class TestRepoStats:
    """Test the repository stats component."""

    def test_clone_url_visible(self, app_url: str, page: Page) -> None:
        """Test that the clone URL and copy button are visible.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        _push_test_repo(app_url, "uitest/clonerepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/uitest/clonerepo")

        expect(page.get_by_test_id("file-tree")).to_be_visible(timeout=15000)

        # Verify repo stats area
        expect(page.get_by_test_id("repo-stats")).to_be_visible()

        # Verify clone URL input
        clone_url = page.get_by_test_id("clone-url")
        expect(clone_url).to_be_visible()
        expect(clone_url).to_have_value(f"{app_url}/uitest/clonerepo.git")

        # Verify copy button
        expect(page.get_by_test_id("copy-clone-url")).to_be_visible()
