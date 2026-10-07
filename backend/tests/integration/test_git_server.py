"""Integration tests for the Git server."""

from __future__ import annotations

import subprocess
import tempfile
import urllib.request
from pathlib import Path


def test_git_push_and_clone(app_url: str) -> None:
    """Test pushing a repository to GitEdge and cloning it back.

    This test:
    1. Creates a local Git repository with some commits
    2. Pushes it to the GitEdge server
    3. Clones it back from GitEdge
    4. Verifies the content matches

    Args:
        wrangler_dev_url: Base URL of the wrangler dev server.
    """
    repo_name = "admin/hello.git"
    remote_url = f"{app_url}/api/v1/{repo_name}"

    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = Path(tmpdir) / "source"
        clone_dir = Path(tmpdir) / "clone"

        source_dir.mkdir()
        _run_git(source_dir, ["init", "-b", "main"])
        _run_git(source_dir, ["config", "user.email", "test@example.com"])
        _run_git(source_dir, ["config", "user.name", "Test User"])

        readme = source_dir / "README.md"
        readme.write_text("# Hello GitEdge\n\nThis is a test repository.\n")
        _run_git(source_dir, ["add", "README.md"])
        _run_git(source_dir, ["commit", "-m", "Initial commit"])

        src_dir = source_dir / "src"
        src_dir.mkdir()
        main_py = src_dir / "main.py"
        main_py.write_text('print("Hello, World!")\n')
        _run_git(source_dir, ["add", "src/main.py"])
        _run_git(source_dir, ["commit", "-m", "Add main.py"])

        source_log = _run_git(source_dir, ["log", "--oneline"])

        _run_git(source_dir, ["remote", "add", "origin", remote_url])
        _run_git(source_dir, ["push", "-u", "origin", "main"])

        _run_git(Path(tmpdir), ["clone", remote_url, "clone"])

        assert clone_dir.exists(), "Clone directory should exist"
        assert (clone_dir / "README.md").exists(), "README.md should exist"
        assert (clone_dir / "src" / "main.py").exists(), "src/main.py should exist"

        cloned_readme = (clone_dir / "README.md").read_text()
        assert "Hello GitEdge" in cloned_readme, "README should contain expected content"

        cloned_main = (clone_dir / "src" / "main.py").read_text()
        assert 'print("Hello, World!")' in cloned_main, "main.py should contain expected content"

        clone_log = _run_git(clone_dir, ["log", "--oneline"])
        assert source_log == clone_log, "Commit history should match"


def test_git_push_to_new_branch(app_url: str) -> None:
    """Test pushing to a new branch and fetching it.

    Args:
        wrangler_dev_url: Base URL of the wrangler dev server.
    """
    repo_name = "admin/branches.git"
    remote_url = f"{app_url}/api/v1/{repo_name}"

    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = Path(tmpdir) / "source"
        clone_dir = Path(tmpdir) / "clone"

        source_dir.mkdir()
        _run_git(source_dir, ["init", "-b", "main"])
        _run_git(source_dir, ["config", "user.email", "test@example.com"])
        _run_git(source_dir, ["config", "user.name", "Test User"])

        readme = source_dir / "README.md"
        readme.write_text("# Branch Test\n")
        _run_git(source_dir, ["add", "README.md"])
        _run_git(source_dir, ["commit", "-m", "Initial commit"])

        _run_git(source_dir, ["remote", "add", "origin", remote_url])
        _run_git(source_dir, ["push", "-u", "origin", "main"])

        _run_git(source_dir, ["checkout", "-b", "feature"])
        feature_file = source_dir / "feature.txt"
        feature_file.write_text("New feature\n")
        _run_git(source_dir, ["add", "feature.txt"])
        _run_git(source_dir, ["commit", "-m", "Add feature"])
        _run_git(source_dir, ["push", "-u", "origin", "feature"])

        _run_git(Path(tmpdir), ["clone", remote_url, "clone"])

        branches = _run_git(clone_dir, ["branch", "-r"])
        assert "origin/main" in branches, "origin/main should exist"
        assert "origin/feature" in branches, "origin/feature should exist"

        _run_git(clone_dir, ["checkout", "feature"])
        assert (clone_dir / "feature.txt").exists(), "feature.txt should exist on feature branch"


def test_info_refs_endpoint(app_url: str) -> None:
    """Test the info/refs endpoint directly.

    Args:
        wrangler_dev_url: Base URL of the wrangler dev server.
    """
    repo_name = "admin/info-refs.git"
    remote_url = f"{app_url}/api/v1/{repo_name}"

    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = Path(tmpdir) / "source"

        source_dir.mkdir()
        _run_git(source_dir, ["init", "-b", "main"])
        _run_git(source_dir, ["config", "user.email", "test@example.com"])
        _run_git(source_dir, ["config", "user.name", "Test User"])

        readme = source_dir / "README.md"
        readme.write_text("# Test\n")
        _run_git(source_dir, ["add", "README.md"])
        _run_git(source_dir, ["commit", "-m", "Initial"])
        _run_git(source_dir, ["remote", "add", "origin", remote_url])
        _run_git(source_dir, ["push", "-u", "origin", "main"])

    info_refs_url = f"{remote_url}/info/refs?service=git-upload-pack"
    req = urllib.request.Request(info_refs_url)
    with urllib.request.urlopen(req, timeout=30) as response:
        content = response.read().decode("utf-8")
        # Should contain service advertisement and refs
        assert "git-upload-pack" in content, "Response should advertise git-upload-pack"
        assert "refs/heads/main" in content, "Response should contain refs/heads/main"


def _run_git(cwd: Path, args: list[str]) -> str:
    """Run a git command and return its output.

    Args:
        cwd: Working directory for the command.
        args: Git command arguments.

    Returns:
        Command stdout as string.

    Raises:
        subprocess.CalledProcessError: If command fails.
    """
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()
