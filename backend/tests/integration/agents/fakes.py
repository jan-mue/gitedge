"""Trusted subprocess sandbox double for testing backend orchestration only."""

import asyncio
from typing import TYPE_CHECKING, override

from pydantic_ai.workspaces import CommandResult

from app.clients.sandbox import SnapshotableSandboxClient

if TYPE_CHECKING:
    from pathlib import Path


class FilesystemTestSandbox(SnapshotableSandboxClient):
    def __init__(self, root: Path) -> None:
        self.root = root

    @override
    async def start(self, name: str, snapshot_id: str | None = None) -> None:
        pass

    @override
    async def snapshot(self, snapshot_id: str) -> str:
        return snapshot_id

    @override
    async def execute(self, command: str, *, timeout: float = 300) -> CommandResult:
        command = command.replace("/opt/gitedge", str(self.root / "state")).replace("/workspace", str(self.root))
        process = await asyncio.create_subprocess_exec(
            "bash", "-c", command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
        return CommandResult(exit_code=int(process.returncode or 0), stdout=stdout.decode(), stderr=stderr.decode())

    @override
    async def stop(self) -> None:
        pass


class MemoryAgentStreams:
    def __init__(self) -> None:
        self.records: dict[tuple[str, str], str] = {}
        self.cancelled_runs: set[str] = set()
        self.attempts: dict[tuple[str, int], int] = {}

    async def append(self, run_id: str, event_id: str, event: str) -> str:
        self.records.setdefault((run_id, event_id), event)
        return event_id

    async def history(self, run_id: str) -> list[str]:
        return [value for (key, _event_id), value in self.records.items() if key == run_id]

    async def attempt(self, run_id: str, step: int) -> int:
        key = (run_id, step)
        self.attempts[key] = self.attempts.get(key, 0) + 1
        return self.attempts[key]

    async def cancelled(self, run_id: str) -> bool:
        return run_id in self.cancelled_runs
