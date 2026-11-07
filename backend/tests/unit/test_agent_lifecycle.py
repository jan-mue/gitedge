from typing import TYPE_CHECKING

from pydantic_ai.workspaces import CommandResult

from app.agents.sandbox import RunSandbox
from app.clients.sandbox import SnapshotableSandboxClient

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


async def test_replay_without_tool_steps_only_stops_existing_machine(mocker: MockerFixture) -> None:
    provider = mocker.AsyncMock(spec=SnapshotableSandboxClient)
    sandbox = RunSandbox(lambda: provider, "run-1", "image-1")
    await sandbox.stop()
    provider.start.assert_not_called()
    provider.stop_named.assert_awaited_once_with("run-1")


async def test_tool_provisions_once_and_snapshots_before_stop(mocker: MockerFixture) -> None:
    provider = mocker.AsyncMock(spec=SnapshotableSandboxClient)
    provider.execute.return_value = CommandResult(exit_code=0, stdout="hello", stderr="")
    provider.snapshot.return_value = "image-2"
    sandbox = RunSandbox(lambda: provider, "run-1", "image-1")
    assert (await sandbox.execute("echo hello")).stdout == "hello"
    assert await sandbox.snapshot("next") == "image-2"
    await sandbox.stop()
    provider.start.assert_awaited_once_with("run-1", "image-1")
    provider.stop.assert_awaited_once()
