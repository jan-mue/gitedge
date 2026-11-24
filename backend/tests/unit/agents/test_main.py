import inspect
import json
import uuid
from typing import TYPE_CHECKING

import pytest
import restate
from anyio import Path as AsyncPath
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic_ai.models.test import TestModel
from pydantic_ai.workspaces import WorkspaceBackend, WorkspaceError, WorkspaceRef
from sqlalchemy.ext.asyncio import AsyncSession
from vercel.sandbox import Sandbox, SandboxClient

from app.agents.dependencies import AgentForgeScope, AgentSessionDeps, CodingAgentDeps, SetupAgentDeps
from app.agents.main import (
    agent_sessions,
    run,
    run_agent_turn,
    snapshot_workspace,
    stop_workspace,
    workspace_backend,
)
from app.clients.agent_repositories import prepare_environment
from app.clients.agent_streams import AgentStreamStore
from app.clients.agent_traces import capture_traces, capture_worktrees
from app.clients.agents import AgentStore
from app.clients.blob_storage import BlobStorageClient
from app.entities.agents import AgentRun, AgentSession
from app.sandboxes.vercel import VercelSandboxBackend

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from pytest_mock import MockerFixture

    from app.schemas.agent_turns import AgentTurnRequest


@pytest.mark.parametrize("cleanup_failure", ["snapshot", "stop"])
async def test_permanent_error_records_terminal_status_despite_failed_cleanup(
    mocker: MockerFixture, cleanup_failure: str
) -> None:
    session = AgentSession(id=uuid.uuid4(), user_id=uuid.uuid4(), environment_id=uuid.uuid4(), kind="coding")
    turn = AgentRun(id=uuid.uuid4(), session_id=session.id, model="local:model", status="pending")
    db = mocker.create_autospec(AsyncSession, instance=True)
    store = AgentStore(db)
    mocker.patch.object(store, "run", return_value=turn)
    mocker.patch.object(store, "get", return_value=session)
    machine = mocker.create_autospec(WorkspaceBackend, instance=True)
    machine.ref = WorkspaceRef(provider="smol", id="test-vm")
    mocker.patch("app.agents.main.workspace_backend", return_value=machine)
    mocker.patch("app.agents.main.capture_worktrees", return_value=[])
    mocker.patch("app.agents.main.configure_git")
    mocker.patch("app.agents.main.run_coding_agent", side_effect=WorkspaceError("private damaged-output details"))
    snapshot = mocker.patch("app.agents.main.snapshot_workspace", return_value="checkpoint")
    stop = mocker.patch("app.agents.main.stop_workspace")
    if cleanup_failure == "snapshot":
        snapshot.side_effect = WorkspaceError("snapshot unavailable")
    else:
        stop.side_effect = restate.TerminalError("stop unavailable")
    streams = mocker.create_autospec(AgentStreamStore, instance=True)
    streams.cancelled.return_value = False
    deps = SetupAgentDeps(streams=streams, blobs=mocker.Mock(), sandbox=mocker.Mock())
    ctx = mocker.create_autospec(restate.ObjectContext, instance=True)
    ctx.key.return_value = str(session.id)

    async def execute(name: str, action: Callable[[], Awaitable[object]], _options: restate.RunOptions) -> object:
        if name == "load authorized turn":
            return {
                "status": "pending",
                "prompt": "work",
                "model": "local:model",
                "user_id": str(session.user_id),
                "author_name": "Test User",
                "author_email": "test@example.com",
                "snapshot": None,
                "setup": False,
                "instructions": "",
                "history": [],
                "repositories": [],
            }
        return await action()

    ctx.run_typed.side_effect = execute

    async def invoke(_handler: object, *, arg: AgentTurnRequest) -> object:
        coding = CodingAgentDeps(
            streams=deps.streams,
            blobs=deps.blobs,
            sandbox=mocker.Mock(),
            forge=mocker.Mock(),
            forge_scope=AgentForgeScope(
                user_id=arg.user_id, session_id=uuid.UUID(arg.session_id), repository_ids=tuple(arg.repository_ids)
            ),
        )
        return await run_agent_turn(ctx, arg, deps=coding, model=TestModel())

    ctx.service_call.side_effect = invoke
    resources = AgentSessionDeps(
        store=store, users=mocker.Mock(), repositories=mocker.Mock(), authorization=mocker.Mock(), agent=deps
    )
    assert await run(ctx, str(turn.id), resources=resources) == str(turn.id)
    assert turn.status == "failed"
    assert turn.error == "WorkspaceError"
    assert turn.finished_at is not None
    terminal = json.loads(streams.append.call_args.args[2])
    assert terminal["type"] == "RUN_ERROR"
    assert terminal["code"] == "WorkspaceError"
    assert "private" not in terminal["message"]
    stop.assert_awaited_once()


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
    deps = SetupAgentDeps(streams=streams, blobs=blobs, sandbox=capability)
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
    deps = SetupAgentDeps(streams=streams, blobs=blobs, sandbox=harness.SmolSandbox())
    restore = mocker.patch("smol.AsyncMachine.restore_checkpoint")
    ref = WorkspaceRef(provider="smol", id="pydantic-ai-" + "a" * 32)
    backend = await workspace_backend(deps, "run-1", ref=ref)
    assert backend.ref == ref
    restore.assert_not_awaited()


@pytest.mark.parametrize(
    "callback",
    [
        prepare_environment,
        capture_worktrees,
        capture_traces,
        snapshot_workspace,
        stop_workspace,
        AgentStore.save_snapshot,
        AgentStore.save_run,
        AgentStore.start,
        AgentStore.finish,
        AgentStore.fail,
        run_agent_turn,
    ],
)
def test_restate_callback_annotations_resolve_at_runtime(callback: Callable[..., Awaitable[object]]) -> None:
    signature = inspect.signature(callback, eval_str=True)
    assert signature.return_annotation is not inspect.Signature.empty


async def test_replayed_vercel_cleanup_uses_injected_client_without_resuming(mocker: MockerFixture) -> None:
    client = mocker.create_autospec(SandboxClient, instance=True)
    machine = mocker.create_autospec(Sandbox, instance=True)
    client.get_sandbox.return_value = machine
    backend = VercelSandboxBackend(client, name="run-1")
    await stop_workspace(backend)
    client.get_sandbox.assert_awaited_once_with(name="run-1")
    client.get_or_create_sandbox.assert_not_awaited()
    machine.stop.assert_awaited_once()


async def test_vercel_uses_native_snapshots(mocker: MockerFixture) -> None:
    client = mocker.create_autospec(SandboxClient, instance=True)
    machine = mocker.create_autospec(Sandbox, instance=True)
    machine.snapshot.return_value = mocker.Mock(id="native-snapshot")
    backend = VercelSandboxBackend(client, name="run-1")
    backend.machine = machine
    assert await snapshot_workspace(backend) == "native-snapshot"
    machine.snapshot.assert_awaited_once_with()


def test_discovery_advertises_bounded_invocation_retries() -> None:
    app = FastAPI()
    app.mount("/restate", restate.app(services=[agent_sessions], protocol="request_response"))
    with TestClient(app) as client:
        response = client.get(
            "/restate/discover", headers={"Accept": "application/vnd.restate.endpointmanifest.v4+json"}
        )
    assert response.status_code == 200
    service = response.json()["services"][0]
    assert service["retryPolicyMaxAttempts"] == 3
    assert service["retryPolicyOnMaxAttempts"] == "PAUSE"
