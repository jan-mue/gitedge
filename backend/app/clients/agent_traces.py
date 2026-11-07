"""Capture line attribution independently of chat message storage."""

import re
import shlex
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    import uuid

    from app.clients.sandbox import SandboxClient


class TraceFile(TypedDict):
    """One generated file range in an Agent Trace record."""

    path: str
    start_line: int
    end_line: int


class RepositoryTrace(TypedDict):
    """Normalized input to the attribution store."""

    repository_id: str
    revision: str
    files: list[TraceFile]


async def capture_worktrees(sandbox: SandboxClient, repository_ids: list[uuid.UUID]) -> dict[str, str]:
    """Record working trees with a temporary index, preserving the user's staging area."""
    trees: dict[str, str] = {}
    for repository_id in repository_ids:
        root = f"/workspace/{repository_id}"
        index = f"/opt/gitedge/trace-{repository_id}.index"
        command = f"cd {shlex.quote(root)} && export GIT_INDEX_FILE={index}; git read-tree HEAD && git add -A && git write-tree"
        result = await sandbox.execute(command)
        if result.exit_code:
            raise RuntimeError(result.stderr)
        trees[str(repository_id)] = result.stdout.strip()
    return trees


async def capture_traces(
    sandbox: SandboxClient, repository_ids: list[uuid.UUID], baseline: dict[str, str]
) -> list[RepositoryTrace]:
    """Attribute this turn's changes, including new files, rather than the whole session."""
    traces: list[RepositoryTrace] = []
    current = await capture_worktrees(sandbox, repository_ids)
    for repository_id in repository_ids:
        root = f"/workspace/{repository_id}"
        before = shlex.quote(baseline[str(repository_id)])
        after = shlex.quote(current[str(repository_id)])
        result = await sandbox.execute(
            f"cd {shlex.quote(root)} && git rev-parse HEAD && git diff --no-ext-diff --no-color --unified=0 {before} {after} --"
        )
        if result.exit_code:
            raise RuntimeError(result.stderr)
        revision, _, diff = result.stdout.partition("\n")
        path = ""
        files: list[TraceFile] = []
        for line in diff.splitlines():
            if line.startswith("+++ b/"):
                path = line[6:]
            elif path and (match := re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)):
                start, count = int(match[1]), int(match[2] or 1)
                if start > 0 and count > 0:
                    files.append(TraceFile(path=path, start_line=start, end_line=start + count - 1))
        traces.append(RepositoryTrace(repository_id=str(repository_id), revision=revision, files=files))
    return traces
