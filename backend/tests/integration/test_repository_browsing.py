"""Integration tests for repository browsing UI."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from playwright.sync_api import expect

from tests.integration.conftest import log_in_user

if TYPE_CHECKING:
    from playwright.sync_api import Page


SUPERUSER_EMAIL = "admin@example.com"
SUPERUSER_PASSWORD = "changethis_admin_password_secure"


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


def _push_test_repo(wrangler_dev_url: str, repo_name: str, extra_files: dict[str, str] | None = None) -> None:
    """Push a test repository with known files to the server.

    Creates a repo with:
    - README.md (markdown file)
    - src/ (directory)
    - src/main.py (Python file)
    - src/utils.py (Python file)

    Args:
        wrangler_dev_url: Base URL of the wrangler dev server.
        repo_name: Repository name (e.g., "admin/browse-test.git").
    """
    remote_url = f"{wrangler_dev_url}/api/v1/{repo_name}"

    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = Path(tmpdir) / "source"
        source_dir.mkdir()

        _run_git(source_dir, ["init", "-b", "main"])
        _run_git(source_dir, ["config", "user.email", "test@example.com"])
        _run_git(source_dir, ["config", "user.name", "Test User"])

        readme = source_dir / "README.md"
        readme.write_text("# Browse Test\n\nA test repository for browsing.\n")

        src_dir = source_dir / "src"
        src_dir.mkdir()

        main_py = src_dir / "main.py"
        main_py.write_text('def main():\n    print("Hello, World!")\n\n\nif __name__ == "__main__":\n    main()\n')

        utils_py = src_dir / "utils.py"
        utils_py.write_text('def add(a: int, b: int) -> int:\n    """Add two numbers."""\n    return a + b\n')

        for path, content in (extra_files or {}).items():
            file = source_dir / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(content)

        _run_git(source_dir, ["add", "."])
        _run_git(source_dir, ["commit", "-m", "Initial commit with test files"])
        _run_git(source_dir, ["remote", "add", "origin", remote_url])
        _run_git(source_dir, ["push", "-u", "--force", "origin", "main"])


class TestRepositoryBrowsing:
    """Test browsing a repository's file tree via the UI."""

    def test_source_language_statistics_only_load_at_root(self, app_url: str, page: Page) -> None:
        sources = {"src/main.ts": "const answer = 42;\n", "src/view.tsx": "export const View = () => <p>Hello</p>;\n"}
        _push_test_repo(
            app_url,
            "admin/languagerepo.git",
            extra_files={
                **sources,
                "package.json": '{"name":"example"}',
                "bun.lock": '{"lockfileVersion":1}',
                "vendor/library.js": "const vendor = 42;\n" * 100,
                "dist/bundle.js": "const bundle = 42;\n" * 100,
            },
        )
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        requests: list[str] = []
        page.on("request", lambda request: requests.append(request.url) if "/statistics?" in request.url else None)
        page.goto(f"{app_url}/admin/languagerepo/src/branch/main/src")
        expect(page.get_by_test_id("tree-entry-view.tsx")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("branch-selector")).to_be_visible()
        assert requests == []

        with page.expect_response(lambda response: "/statistics?" in response.url) as response:
            page.goto(f"{app_url}/admin/languagerepo")
        statistics = response.value.json()
        languages = {language["name"]: language for language in statistics["languages"]}
        assert set(languages) == {"TypeScript", "Python"}
        assert languages["TypeScript"]["size"] == sum(len(content) for content in sources.values())
        button = page.get_by_role("button", name=f"TypeScript: {languages['TypeScript']['percentage']}%")
        expect(button).to_be_visible()
        page.get_by_test_id("tree-entry-src").click()
        expect(page.get_by_test_id("tree-entry-view.tsx")).to_be_visible()
        expect(button).to_have_count(0)
        assert len(requests) == 1
        page.go_back()
        expect(button).to_be_visible()
        assert len(requests) == 1

    def test_repository_appears_in_list(self, app_url: str, page: Page) -> None:
        """Test that a pushed repository appears in the repositories list.

        Args:
            wrangler_dev_url: Base URL of the wrangler dev server.
            page: Playwright page.
        """
        _push_test_repo(app_url, "admin/listrepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/repositories")

        # Verify the repository appears in the list (use test_id to avoid matching multiple elements)
        expect(page.get_by_test_id("repo-link-listrepo")).to_be_visible(timeout=10000)

    def test_browse_repository_root(self, app_url: str, page: Page) -> None:
        """Test browsing the root of a repository shows files and directories.

        Args:
            wrangler_dev_url: Base URL of the wrangler dev server.
            page: Playwright page.
        """
        _push_test_repo(app_url, "admin/rootrepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/admin/rootrepo")

        file_tree = page.get_by_test_id("file-tree")
        expect(file_tree).to_be_visible(timeout=15000)

        expect(page.get_by_test_id("tree-entry-src")).to_be_visible()
        expect(page.get_by_test_id("tree-entry-README.md")).to_be_visible()

    def test_browse_subdirectory(self, app_url: str, page: Page) -> None:
        """Test browsing into a subdirectory.

        Args:
            wrangler_dev_url: Base URL of the wrangler dev server.
            page: Playwright page.
        """
        _push_test_repo(app_url, "admin/subdirrepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/admin/subdirrepo")
        expect(page.get_by_test_id("file-tree")).to_be_visible(timeout=15000)

        page.get_by_test_id("tree-entry-src").click()

        expect(page.get_by_test_id("tree-entry-main.py")).to_be_visible(timeout=10000)
        expect(page.get_by_test_id("tree-entry-utils.py")).to_be_visible()

        expect(page.get_by_test_id("tree-entry-parent")).to_be_visible()

    def test_navigate_to_repo_from_list(self, app_url: str, page: Page) -> None:
        """Test clicking a repo name in the list navigates to the repo browser.

        Args:
            wrangler_dev_url: Base URL of the wrangler dev server.
            page: Playwright page.
        """
        _push_test_repo(app_url, "admin/navrepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        page.goto(f"{app_url}/repositories")

        repo_link = page.get_by_test_id("repo-link-navrepo")
        expect(repo_link).to_be_visible(timeout=10000)
        repo_link.click()

        expect(page.get_by_test_id("file-tree")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("tree-entry-README.md")).to_be_visible()


class TestFileViewer:
    """Test viewing individual files with syntax highlighting."""

    def test_view_python_file(self, app_url: str, page: Page) -> None:
        """Test viewing a Python file shows syntax-highlighted content.

        Args:
            wrangler_dev_url: Base URL of the wrangler dev server.
            page: Playwright page.
        """
        _push_test_repo(app_url, "admin/viewrepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/admin/viewrepo/src/branch/main/src")
        expect(page.get_by_test_id("file-tree")).to_be_visible(timeout=15000)

        page.get_by_test_id("tree-entry-main.py").click()

        file_viewer = page.get_by_test_id("file-viewer")
        expect(file_viewer).to_be_visible(timeout=15000)

        expect(page.get_by_test_id("file-name")).to_have_text("main.py")
        expect(page.get_by_test_id("file-language")).to_have_text("Python")

        content = page.get_by_test_id("highlighted-content")
        expect(content).to_be_visible()
        expect(content).to_contain_text("Hello, World!")

    def test_view_markdown_file(self, app_url: str, page: Page) -> None:
        """Test viewing a Markdown file.

        Args:
            wrangler_dev_url: Base URL of the wrangler dev server.
            page: Playwright page.
        """
        _push_test_repo(app_url, "admin/mdrepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/admin/mdrepo")
        expect(page.get_by_test_id("file-tree")).to_be_visible(timeout=15000)

        page.get_by_test_id("tree-entry-README.md").click()

        expect(page.get_by_test_id("file-viewer")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("file-name")).to_have_text("README.md")

        content = page.get_by_test_id("highlighted-content")
        expect(content).to_contain_text("Browse Test")

    def test_back_button_returns_to_tree(self, app_url: str, page: Page) -> None:
        """Test that the Back button returns to the file tree.

        Args:
            wrangler_dev_url: Base URL of the wrangler dev server.
            page: Playwright page.
        """
        _push_test_repo(app_url, "admin/backrepo.git")

        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.goto(f"{app_url}/admin/backrepo")
        expect(page.get_by_test_id("file-tree")).to_be_visible(timeout=15000)
        page.get_by_test_id("tree-entry-README.md").click()
        expect(page.get_by_test_id("file-viewer")).to_be_visible(timeout=15000)

        page.get_by_role("button", name="Back").click()

        expect(page.get_by_test_id("file-tree")).to_be_visible(timeout=10000)
        expect(page.get_by_test_id("tree-entry-README.md")).to_be_visible()
