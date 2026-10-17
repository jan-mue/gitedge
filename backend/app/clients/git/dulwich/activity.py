"""Pure aggregation of repository Git history for activity views."""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, cast

from dulwich.diff_tree import tree_changes
from dulwich.objects import Commit
from dulwich.patch import write_commit_diff

from app.schemas.repository_activity import (
    GitActivityCommit,
    GitActivityHistory,
)

if TYPE_CHECKING:
    from app.clients.git.dulwich.blob_repository import BlobRepository


def _line_changes(repo: BlobRepository, commit: Commit) -> tuple[int, int, list[str]]:
    """Count changed lines in diff hunks, including the initial commit."""
    parent_tree = cast(Commit, repo.object_store[commit.parents[0]]).tree if commit.parents else None
    files = {
        entry.path.decode("utf-8", errors="replace")
        for change in tree_changes(repo.object_store, parent_tree, commit.tree)
        if (entry := change.new or change.old) is not None and entry.path is not None
    }
    buffer = BytesIO()
    write_commit_diff(buffer, repo.object_store, commit)
    additions = deletions = 0
    in_hunk = False
    for line in buffer.getvalue().splitlines():
        if line.startswith(b"diff --git "):
            in_hunk = False
        elif line.startswith(b"@@ "):
            in_hunk = True
        elif in_hunk:
            additions += line.startswith(b"+")
            deletions += line.startswith(b"-")
    return additions, deletions, sorted(files)


def collect_git_activity(repo: BlobRepository, default_branch: str) -> GitActivityHistory:
    """Collect each commit once across branches; ignore merge diffs."""
    refs = repo.refs.as_dict()
    default_sha = refs.get(f"refs/heads/{default_branch}".encode())
    default_commits = {entry.commit.id for entry in repo.get_walker(include=[default_sha])} if default_sha else set()
    heads = sorted({sha for ref, sha in refs.items() if ref.startswith(b"refs/heads/")})
    commits: list[GitActivityCommit] = []
    if not heads:
        return GitActivityHistory(default_branch=default_branch)
    for entry in repo.get_walker(include=heads):
        commit = entry.commit
        raw_author = commit.author.decode("utf-8", errors="replace")
        name, separator, email = raw_author.rpartition(" <")
        is_merge = len(commit.parents) > 1
        additions, deletions, files = (0, 0, []) if is_merge else _line_changes(repo, commit)
        commits.append(
            GitActivityCommit(
                sha=commit.id.decode(),
                message=commit.message.decode("utf-8", errors="replace").strip(),
                author=name if separator else raw_author,
                author_email=email.removesuffix(">") if separator else "",
                timestamp=commit.commit_time,
                is_default=commit.id in default_commits,
                is_merge=is_merge,
                additions=additions,
                deletions=deletions,
                files=files,
            )
        )
    commits.sort(key=lambda commit: (commit.timestamp, commit.sha), reverse=True)
    return GitActivityHistory(default_branch=default_branch, commits=commits)
