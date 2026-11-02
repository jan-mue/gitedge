from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import httpx2

from tests.conftest import FIRST_SUPERUSER, FIRST_SUPERUSER_PASSWORD


def run_git(cwd: Path, args: list[str]) -> str:
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


def push_repo(
    app_url: str,
    repo_name: str,
    *,
    extra_branches: tuple[str, ...] = (),
    tag: str | None = None,
    with_deletions: bool = False,
) -> None:
    """Push a test repository with a README, a source file, optional branches and a tag.

    Args:
        app_url: Base URL of the GitEdge server.
        repo_name: Repository path (e.g. "testuser/repo.git").
        extra_branches: Additional branches to create and push.
        tag: Optional tag to create and push.
        with_deletions: Add a default-branch commit that replaces existing lines.
    """
    remote_url = f"{app_url}/api/v1/{repo_name}"

    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = Path(tmpdir) / "source"
        source_dir.mkdir()

        run_git(source_dir, ["init", "-b", "main"])
        run_git(source_dir, ["config", "user.email", "test@example.com"])
        run_git(source_dir, ["config", "user.name", "Test User"])

        (source_dir / "README.md").write_text("# Test Repository\n\nA test repository.\n")
        src_dir = source_dir / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text('print("Hello, World!")\n')

        run_git(source_dir, ["add", "."])
        run_git(source_dir, ["commit", "-m", "Initial commit"])
        if with_deletions:
            (source_dir / "README.md").write_text("# Updated repository\nUpdated description.\n")
            run_git(source_dir, ["add", "."])
            run_git(source_dir, ["commit", "-m", "Replace README lines"])
        if tag:
            run_git(source_dir, ["tag", tag])

        configure_git_auth(app_url, repo_name, source_dir)
        run_git(source_dir, ["remote", "add", "origin", remote_url])
        run_git(source_dir, ["push", "-u", "--force", "origin", "main"])
        if tag:
            run_git(source_dir, ["push", "--force", "origin", tag])

        for branch in extra_branches:
            run_git(source_dir, ["checkout", "-b", branch, "main"])
            (source_dir / f"{branch.replace('/', '_')}.txt").write_text(f"{branch}\n")
            run_git(source_dir, ["add", "."])
            run_git(source_dir, ["commit", "-m", f"Add {branch}"])
            run_git(source_dir, ["push", "-u", "--force", "origin", branch])
            run_git(source_dir, ["checkout", "main"])


def superuser_headers(app_url: str) -> dict[str, str]:
    """Authenticate integration setup requests as the seeded administrator."""
    response = httpx2.post(
        f"{app_url}/api/v1/login/access-token", data={"username": FIRST_SUPERUSER, "password": FIRST_SUPERUSER_PASSWORD}
    )
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def configure_git_auth(app_url: str, repo_name: str, source_dir: Path) -> None:
    """Create a repository and authenticate pushes from a temporary checkout."""
    headers = superuser_headers(app_url)
    owner, name = repo_name.removesuffix(".git").split("/")
    response = httpx2.post(f"{app_url}/api/v1/repositories/", json={"owner": owner, "name": name}, headers=headers)
    assert response.status_code in (201, 409), response.text
    result = subprocess.run(
        ["git", "config", "http.extraHeader", f"Authorization: {headers['Authorization']}"],
        cwd=source_dir,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, "Could not configure Git authentication"
