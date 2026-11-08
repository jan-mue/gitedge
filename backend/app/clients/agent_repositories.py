"""Prepare immutable repository bundles without putting forge credentials in tools."""

import io
import shlex
from typing import TYPE_CHECKING

from dulwich.bundle import create_bundle_from_repo, write_bundle
from fastapi.concurrency import run_in_threadpool

if TYPE_CHECKING:
    import uuid
    from collections.abc import Awaitable, Callable

    from pydantic_ai.workspaces import CommandResult

    from app.clients.blob_storage import BlobStorageClient
    from app.clients.git.blob_repository import BlobRepository
    from app.clients.git.repositories import GitClient
    from app.clients.repositories import RepositoryStore
    from app.clients.sandbox import SandboxClient


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


async def prepare_environment(
    sandbox: SandboxClient,
    blobs: BlobStorageClient,
    environment_id: uuid.UUID,
    repository_ids: list[uuid.UUID],
    script: str,
    instructions: str,
    execute: Callable[[str], Awaitable[CommandResult]] | None = None,
) -> list[dict[str, str | int]]:
    """Clone credential-free bundles and persist versioned setup files in each repo."""
    results: list[dict[str, str | int]] = []
    for repository_id in repository_ids:
        image = await blobs.get(f"agents/environments/{environment_id}/{repository_id}.bundle")
        if image is None:
            raise FileNotFoundError("Repository bundle unavailable")
        path = f"/workspace/{repository_id}"
        bundle_path = f"/opt/gitedge/{repository_id}.bundle"
        await sandbox.write_file(bundle_path, image)
        if image:
            command = f"test -d {path}/.git || (rm -rf /opt/gitedge/clone-{repository_id} && git clone {bundle_path} /opt/gitedge/clone-{repository_id} && mv /opt/gitedge/clone-{repository_id} {path})"
        else:
            branch = (
                await blobs.get(f"agents/environments/{environment_id}/{repository_id}.branch") or b"main"
            ).decode()
            command = f"test -d {path}/.git || git init -b {shlex.quote(branch)} {path}"
        result = await sandbox.execute(command)
        if result.exit_code:
            raise RuntimeError(result.stderr)
        initialized = await sandbox.execute(
            f"git -C {path} rev-parse HEAD >/dev/null 2>&1 || git -C {path} -c user.name=GitEdge -c user.email=agents@gitedge.invalid commit --allow-empty -m 'Initialize agent workspace'"
        )
        if initialized.exit_code:
            raise RuntimeError(initialized.stderr)
        if script:
            await sandbox.write_file(f"{path}/.gitedge/agents/setup.sh", script.encode())
        if instructions:
            await sandbox.write_file(f"{path}/.gitedge/agents/instructions.md", instructions.encode())
        command = f"cd {path} && if test -f .gitedge/agents/setup.sh; then bash .gitedge/agents/setup.sh; fi"
        result = await execute(command) if execute else await sandbox.execute(command, timeout=900)
        results.append(
            {
                "repository": str(repository_id),
                "exit_code": result.exit_code,
                "output": (result.stdout + result.stderr)[-4000:],
            }
        )
    return results
