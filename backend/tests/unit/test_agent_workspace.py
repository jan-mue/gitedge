import asyncio
from typing import TYPE_CHECKING, override

import pytest
from pydantic_ai.workspaces import CommandResult

from app.agents.workspace import SandboxWorkspace
from app.clients.sandbox import SandboxClient, SnapshotableSandboxClient

if TYPE_CHECKING:
    from pathlib import Path


class LocalTestSandbox(SandboxClient):
    @override
    async def execute(self, command: str, *, timeout: float = 300) -> CommandResult:
        process = await asyncio.create_subprocess_exec(
            "bash", "-c", command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
        return CommandResult(exit_code=int(process.returncode or 0), stdout=stdout.decode(), stderr=stderr.decode())

    @override
    async def stop(self) -> None:
        pass


def test_snapshot_contract_is_separate() -> None:
    assert not issubclass(LocalTestSandbox, SnapshotableSandboxClient)


async def test_workspace_requires_shell_for_string() -> None:
    async def output(stream: str, chunk: str, _command_id: str, _sequence: int) -> None:
        pass

    workspace = SandboxWorkspace(LocalTestSandbox(), "test", output)
    with pytest.raises(TypeError):
        await workspace.run("echo unsafe")


async def test_command_receipt_reattaches_without_reexecuting(tmp_path: Path) -> None:
    class TestSandbox(LocalTestSandbox):
        @override
        async def execute(self, command: str, *, timeout: float = 300) -> CommandResult:
            return await super().execute(
                command.replace("/opt/gitedge", str(tmp_path / "state")).replace("/workspace", str(tmp_path)),
                timeout=timeout,
            )

    output_chunks = []

    async def output(stream: str, chunk: str, _command_id: str, _sequence: int) -> None:
        output_chunks.append((stream, chunk))

    command = "echo called >> count; echo hello; echo warning >&2; exit 7"
    first = SandboxWorkspace(TestSandbox(), "receipt-test", output)
    result = await first.run(command, shell=True)
    second = SandboxWorkspace(TestSandbox(), "receipt-test", output)
    replayed = await second.run(command, shell=True)
    assert result == replayed
    assert result.exit_code == 7
    assert result.stdout == "hello\n"
    assert result.stderr == "warning\n"
    assert (tmp_path / "count").read_text() == "called\n"
    assert ("stdout", "hello\n") in output_chunks
