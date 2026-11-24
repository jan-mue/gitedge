"""Publish native Git commits without modifying a branch, index, or dirty worktree."""

import uuid
from typing import TYPE_CHECKING

import pytest
from pydantic_ai.workspaces import Workspace
from uncalled_for import FailedDependency, resolved_dependencies

from app.agents.dependencies import get_sources
from app.clients.agent_repositories import configure_git, prepare_environment
from app.exceptions import ConflictError, InvalidInputError
from tests.git import FIRST_SUPERUSER, push_repo

if TYPE_CHECKING:
    from pydantic_ai_harness.smol_sandbox import SmolSandboxBackend


async def test_publication_preserves_real_git_commits_and_uncommitted_changes(
    backend_url: str, agent_sandbox: SmolSandboxBackend
) -> None:
    owner = FIRST_SUPERUSER.split("@")[0]
    name = "native-branch-publication"
    push_repo(backend_url, f"{owner}/{name}.git")
    async with resolved_dependencies(get_sources) as arguments:
        for value in arguments.values():
            if isinstance(value, FailedDependency):
                raise value.error
        sources = get_sources(**arguments)
        repository = await sources.repositories.get_by_owner_and_name(owner, name)
        environment_id, session_id = uuid.uuid4(), uuid.uuid4()
        await sources.export(environment_id, [repository.id])
        await prepare_environment(
            agent_sandbox, sources.blobs, environment_id, [repository.id], "", "Setup metadata is not a coding change."
        )
        await configure_git(agent_sandbox, [repository.id], "Native Git Author", "native@example.com")
        workspace = Workspace(agent_sandbox)
        root = f"/workspace/{repository.id}"
        branch = "docs/native-readme-update"

        async def git(*args: str) -> str:
            result = await workspace.run(["git", "-C", root, *args])
            assert result.exit_code == 0, result.stderr
            return result.stdout.strip()

        base = await git("rev-parse", "HEAD")
        with pytest.raises(InvalidInputError):
            await sources.publish_branch(workspace, repository.id, session_id, "main", "not-created")
        await git("branch", branch)
        await git("switch", branch)
        await workspace.write_text(f"{root}/README.md", "First committed change.\n")
        with pytest.raises(ConflictError, match="no coding changes"):
            await sources.publish_branch(workspace, repository.id, session_id, "main", branch)
        assert await git("rev-parse", "HEAD") == base
        assert await workspace.read_text(f"{root}/README.md") == "First committed change.\n"
        await git("add", "README.md")
        await git("commit", "-m", "First native commit")
        first = await git("rev-parse", "HEAD")
        assert await sources.publish_branch(workspace, repository.id, session_id, "main", branch) == branch
        assert await sources.git.git_refs.branch_heads(owner, name, "main", branch) == (base, first)
        await workspace.write_text(f"{root}/README.md", "Second committed change.\n")
        await git("add", "-A")
        await git("commit", "-m", "Second native commit")
        head = await git("rev-parse", "HEAD")
        index = await git("write-tree")
        await workspace.write_text(f"{root}/README.md", "Uncommitted work stays in the sandbox.\n")

        for _ in range(2):
            assert await sources.publish_branch(workspace, repository.id, session_id, "main", branch) == branch
            assert await git("rev-parse", "HEAD") == head
            assert await git("write-tree") == index
            assert await workspace.read_text(f"{root}/README.md") == "Uncommitted work stays in the sandbox.\n"
        assert await sources.git.git_refs.branch_heads(owner, name, "main", branch) == (base, head)
        commits = await sources.git.list_commits(owner, name, ref=branch)
        assert [commit.sha for commit in commits.data[:2]] == [head, first]
        assert [commit.message.strip() for commit in commits.data[:2]] == [
            "Second native commit",
            "First native commit",
        ]
        assert all(commit.author == "Native Git Author" for commit in commits.data[:2])
        assert all(commit.author_email == "native@example.com" for commit in commits.data[:2])
