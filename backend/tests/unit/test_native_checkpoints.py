from typing import TYPE_CHECKING

import pytest
from anyio import Path as AsyncPath
from pydantic_ai.workspaces import WorkspaceRef

from app.agents.runtime import snapshot_workspace, workspace_backend
from app.api.dependencies import get_coding_agent_deps
from app.clients.agent_streams import AgentStreamStore
from app.clients.blob_storage import BlobStorageClient

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


async def test_smol_snapshot_calls_native_async_checkpoint(mocker: MockerFixture, tmp_path: Path) -> None:
    harness = pytest.importorskip("pydantic_ai_harness.smol_sandbox")
    smol = pytest.importorskip("smol")
    backend = mocker.create_autospec(harness.SmolSandboxBackend, instance=True)
    machine = mocker.create_autospec(smol.AsyncMachine, instance=True)
    backend.get_sandbox.return_value = machine
    machine.checkpoint.return_value = mocker.Mock(id="provider-checkpoint")
    directory = tmp_path / "nested" / "private"
    assert await snapshot_workspace(backend, checkpoint_dir=directory) == "provider-checkpoint"
    assert await AsyncPath(directory).is_dir()
    assert (await AsyncPath(directory).stat()).st_mode & 0o777 == 0o700
    machine.checkpoint.assert_awaited_once()
    path = machine.checkpoint.await_args.args[0]
    assert path.startswith(str(directory))
    assert path.endswith(".smolcheckpoint")


async def test_smol_restore_uses_native_checkpoint_and_upstream_workspace(mocker: MockerFixture) -> None:
    harness = pytest.importorskip("pydantic_ai_harness.smol_sandbox")
    smol = pytest.importorskip("smol")
    streams = mocker.create_autospec(AgentStreamStore, instance=True)
    blobs = mocker.create_autospec(BlobStorageClient, instance=True)
    capability = harness.SmolSandbox(image="python:3.14.10-slim-bookworm")
    deps = get_coding_agent_deps(streams, blobs, capability)
    machine = mocker.create_autospec(smol.AsyncMachine, instance=True)
    machine.id = "pydantic-ai-" + "a" * 32
    restore = mocker.patch("smol.AsyncMachine.restore_checkpoint", return_value=machine)
    backend = await workspace_backend(deps, "run-1", snapshot_id="/private/checkpoint.smolcheckpoint")
    restore.assert_awaited_once()
    assert restore.await_args is not None
    assert restore.await_args.args[0] == "/private/checkpoint.smolcheckpoint"
    assert restore.await_args.args[1].startswith("pydantic-ai-")
    assert restore.await_args.args[2].target == "local"
    assert type(backend) is harness.SmolSandboxBackend
    assert backend.ref == WorkspaceRef(provider="smol", id=machine.id)


async def test_replayed_ref_does_not_restore_or_create_another_vm(mocker: MockerFixture) -> None:
    harness = pytest.importorskip("pydantic_ai_harness.smol_sandbox")
    streams = mocker.create_autospec(AgentStreamStore, instance=True)
    blobs = mocker.create_autospec(BlobStorageClient, instance=True)
    deps = get_coding_agent_deps(streams, blobs, harness.SmolSandbox())
    restore = mocker.patch("smol.AsyncMachine.restore_checkpoint")
    ref = WorkspaceRef(provider="smol", id="pydantic-ai-" + "a" * 32)
    backend = await workspace_backend(deps, "run-1", ref=ref)
    assert backend.ref == ref
    restore.assert_not_awaited()
