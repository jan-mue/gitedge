from typing import TYPE_CHECKING

from vercel.sandbox import Sandbox, SandboxClient

from app.agents.runtime import snapshot_workspace, stop_workspace
from app.sandboxes.vercel import VercelSandboxBackend

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


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
