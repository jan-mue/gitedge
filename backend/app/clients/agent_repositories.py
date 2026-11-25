"""Prepare immutable repository bundles without putting forge credentials in tools."""

import io
import shlex
import uuid  # noqa: TC003 - Restate evaluates run_typed callback annotations
from collections.abc import Awaitable, Callable  # noqa: TC003 - Restate callback annotations
from typing import TYPE_CHECKING

from dulwich.bundle import create_bundle_from_repo, write_bundle
from dulwich.refs import Ref, check_ref_format
from fastapi.concurrency import run_in_threadpool
from pydantic_ai.workspaces import CommandResult, Workspace, WorkspaceBackend

from app.clients.blob_storage import BlobStorageClient  # noqa: TC001 - Restate callback annotations
from app.exceptions import ConflictError, InvalidInputError

if TYPE_CHECKING:
    from app.clients.git.blob_repository import BlobRepository
    from app.clients.git.repositories import GitClient
    from app.clients.repositories import RepositoryStore


class AgentRepositoryClient:
    """Export authorized source repositories into the environment's private storage."""

    def __init__(self, git: GitClient, repositories: RepositoryStore, blobs: BlobStorageClient) -> None:
        """Use existing forge storage and Git clients."""
        self.git = git
        self.repositories = repositories
        self.blobs = blobs

    async def export(self, environment_id: uuid.UUID, repository_ids: list[uuid.UUID]) -> None:
        """Capture a real Git bundle per repository, preserving refs and history."""
        for repository_id in repository_ids:
            repository = await self.repositories.get(repository_id)
            source = await self.git.load_repository(repository.owner.name, repository.name)

            def bundle(source: BlobRepository = source) -> bytes:
                target = io.BytesIO()
                if not source.get_refs():
                    return b""
                write_bundle(target, create_bundle_from_repo(source))
                return target.getvalue()

            await self.blobs.put(
                f"agents/environments/{environment_id}/{repository_id}.bundle", await run_in_threadpool(bundle)
            )
            await self.blobs.put(
                f"agents/environments/{environment_id}/{repository_id}.branch", repository.default_branch.encode()
            )

    async def publish_branch(
        self,
        workspace: Workspace,
        repository_id: uuid.UUID,
        session_id: uuid.UUID,
        base_branch: str,
        branch: str,
    ) -> str:
        """Export an existing committed branch without staging, committing, or rewriting it."""
        repository = await self.repositories.get(repository_id)
        if branch.startswith("-") or not check_ref_format(Ref(f"refs/heads/{branch}".encode())):
            raise InvalidInputError("Invalid publication branch")
        if branch in {base_branch, repository.default_branch}:
            raise InvalidInputError("The publication branch must not replace the base or default branch")
        root = f"/workspace/{repository_id}"
        artifact = f"/opt/gitedge/publication-{repository_id}-{session_id.hex}.bundle"
        script = """
set -euo pipefail
cd "$1"
branch=$2
base_ref=$3
artifact=$4
base=$(git rev-parse --verify "$base_ref^{commit}")
head=$(git rev-parse --verify "refs/heads/$branch^{commit}")
if [ "$head" = "$base" ]; then
  printf 'NO_CHANGES\\n'
  exit 0
fi
if ! git diff --quiet "$base_ref" "refs/heads/$branch" -- .gitedge/agents; then
  printf 'Setup metadata must not be committed to the publication branch.\\n' >&2
  exit 1
fi
git bundle create "$artifact" "refs/heads/$branch" "^$base_ref"
"""
        _base, expected = await self.git.git_refs.branch_heads(
            repository.owner.name, repository.name, base_branch, branch
        )
        result = await workspace.run(
            ["bash", "-c", script, "bash", root, branch, f"refs/remotes/origin/{base_branch}", artifact],
            timeout=300,
        )
        if result.exit_code:
            raise InvalidInputError(result.stderr.strip() or "Create the branch and commit its changes with Git first")
        if result.stdout.strip() == "NO_CHANGES":
            raise ConflictError("There are no coding changes to publish")
        await self.git.publish_agent_bundle(
            repository.owner.name,
            repository.name,
            branch,
            base_branch,
            await workspace.read_bytes(artifact),
            expected,
        )
        return branch


async def configure_git(
    sandbox: WorkspaceBackend, repository_ids: list[uuid.UUID], author_name: str, author_email: str
) -> None:
    """Configure a normal Git identity and ignore application-owned setup metadata."""
    workspace = Workspace(sandbox)
    for repository_id in repository_ids:
        root = f"/workspace/{repository_id}"
        for setting, value in (("user.name", author_name), ("user.email", author_email)):
            result = await workspace.run(["git", "-C", root, "config", setting, value])
            if result.exit_code:
                raise InvalidInputError(result.stderr.strip() or "Unable to configure Git identity")
        exclude = f"{root}/.git/info/exclude"
        contents = await workspace.read_text(exclude)
        if ".gitedge/agents/" not in contents.splitlines():
            await workspace.write_text(exclude, contents.rstrip("\n") + "\n.gitedge/agents/\n")


async def prepare_environment(
    sandbox: WorkspaceBackend,
    blobs: BlobStorageClient,
    environment_id: uuid.UUID,
    repository_ids: list[uuid.UUID],
    script: str,
    instructions: str,
    execute: Callable[[str], Awaitable[CommandResult]] | None = None,
) -> list[dict[str, str | int]]:
    """Clone credential-free bundles and persist versioned setup files in each repo."""
    results: list[dict[str, str | int]] = []
    workspace = Workspace(sandbox)
    for repository_id in repository_ids:
        image = await blobs.get(f"agents/environments/{environment_id}/{repository_id}.bundle")
        if image is None:
            raise FileNotFoundError("Repository bundle unavailable")
        path = f"/workspace/{repository_id}"
        bundle_path = f"/opt/gitedge/{repository_id}.bundle"
        await workspace.write_bytes(bundle_path, image)
        if image:
            command = f"test -d {path}/.git || (rm -rf /opt/gitedge/clone-{repository_id} && git clone {bundle_path} /opt/gitedge/clone-{repository_id} && mv /opt/gitedge/clone-{repository_id} {path})"
        else:
            branch = (
                await blobs.get(f"agents/environments/{environment_id}/{repository_id}.branch") or b"main"
            ).decode()
            command = f"test -d {path}/.git || git init -b {shlex.quote(branch)} {path}"
        result = await workspace.run(["bash", "-c", command], timeout=300)
        if result.exit_code:
            raise RuntimeError(result.stderr)
        initialized = await workspace.run(
            [
                "bash",
                "-c",
                f"git -C {path} rev-parse HEAD >/dev/null 2>&1 || git -C {path} -c user.name=GitEdge -c user.email=agents@gitedge.invalid commit --allow-empty -m 'Initialize agent workspace'",
            ],
            timeout=300,
        )
        if initialized.exit_code:
            raise RuntimeError(initialized.stderr)
        if script:
            await workspace.write_bytes(f"{path}/.gitedge/agents/setup.sh", script.encode())
        if instructions:
            await workspace.write_bytes(f"{path}/.gitedge/agents/instructions.md", instructions.encode())
        command = f"cd {path} && if test -f .gitedge/agents/setup.sh; then bash .gitedge/agents/setup.sh; fi"
        result = await execute(command) if execute else await workspace.run(["bash", "-c", command], timeout=900)
        results.append(
            {
                "repository": str(repository_id),
                "exit_code": result.exit_code,
                "output": (result.stdout + result.stderr)[-4000:],
            }
        )
    return results
