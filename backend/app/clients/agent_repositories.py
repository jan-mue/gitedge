"""Prepare immutable repository bundles without putting forge credentials in tools."""

import io
from typing import TYPE_CHECKING

from dulwich.bundle import create_bundle_from_repo, write_bundle
from starlette.concurrency import run_in_threadpool

if TYPE_CHECKING:
    import uuid

    from app.clients.blob_storage import BlobStorageClient
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

            def bundle() -> bytes:
                target = io.BytesIO()
                write_bundle(target, create_bundle_from_repo(source))  # noqa: B023 - awaited before the loop advances
                return target.getvalue()

            await self.blobs.put(
                f"agents/environments/{environment_id}/{repository_id}.bundle", await run_in_threadpool(bundle)
            )


async def prepare_environment(
    sandbox: SandboxClient,
    blobs: BlobStorageClient,
    environment_id: uuid.UUID,
    repository_ids: list[uuid.UUID],
    script: str,
    instructions: str,
) -> None:
    """Clone credential-free bundles and persist versioned setup files in each repo."""
    for repository_id in repository_ids:
        image = await blobs.get(f"agents/environments/{environment_id}/{repository_id}.bundle")
        if image is None:
            raise FileNotFoundError("Repository bundle unavailable")
        path = f"/workspace/{repository_id}"
        bundle_path = f"/opt/gitedge/{repository_id}.bundle"
        await sandbox.write_file(bundle_path, image)
        command = f"test -d {path}/.git || git clone {bundle_path} {path}"
        result = await sandbox.execute(command)
        if result.exit_code:
            raise RuntimeError(result.stderr)
        if script:
            await sandbox.write_file(f"{path}/.gitedge/agents/setup.sh", script.encode())
        if instructions:
            await sandbox.write_file(f"{path}/.gitedge/agents/instructions.md", instructions.encode())
        result = await sandbox.execute(
            f"cd {path} && if test -f .gitedge/agents/setup.sh; then bash .gitedge/agents/setup.sh; fi", timeout=900
        )
        if result.exit_code:
            raise RuntimeError(result.stderr)
