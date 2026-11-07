"""Harness workspace with reattachable command execution in a remote sandbox."""

import asyncio
import hashlib
import json
import shlex
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from pydantic_ai._run_context import get_current_run_context
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.workspaces import CommandResult, WorkspaceBackend, WorkspaceCommand, WorkspaceRef

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pydantic_ai import RunContext

    from app.clients.sandbox import OutputSink, SandboxClient


class SandboxWorkspace:
    """Run shell tools remotely; command receipts survive backend process loss."""

    def __init__(self, sandbox: SandboxClient, name: str, output: OutputSink) -> None:
        """Bind one run's machine and persist-before-send output callback."""
        self.sandbox = sandbox
        self.name = name
        self.output = output
        self.sequence = 0
        self.command_id = ""

    @property
    def ref(self) -> WorkspaceRef:
        """Return the stable workspace reference recorded in model history."""
        return WorkspaceRef(provider="gitedge", id=self.name)

    async def working_dir(self) -> str:
        """All repository collections live under this directory."""
        return "/workspace"

    async def run(
        self,
        command: WorkspaceCommand,
        *,
        shell: bool = False,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,  # noqa: ASYNC109 - remote command protocol
    ) -> CommandResult:
        """Start once under flock, then poll saved output and exit status.

        The helper process is detached from the API call; a retry reattaches via
        the deterministic command directory instead of running the shell again.
        """
        if isinstance(command, str) != shell:
            raise TypeError("String commands require shell=True")
        script = command if isinstance(command, str) else shlex.join(command)
        environment = " ".join(shlex.quote(f"{key}={value}") for key, value in (env or {}).items())
        self.sequence += 1
        context = get_current_run_context()
        call_id = context.tool_call_id if context else str(self.sequence)
        self.command_id = hashlib.sha256(
            json.dumps([call_id, script, dict(env or {})], sort_keys=True).encode()
        ).hexdigest()
        receipt = f"/opt/gitedge/commands/{self.name}/{self.command_id}"
        inner = f"cd /workspace && env {environment} timeout {timeout or 300} bash -c {shlex.quote(script)}"
        runner = f"{inner} >{receipt}/stdout 2>{receipt}/stderr; echo $? >{receipt}/exit.tmp; mv {receipt}/exit.tmp {receipt}/exit"
        launch = f"mkdir -p {receipt}; flock -n {receipt}/lock bash -c {shlex.quote(f'test -e {receipt}/started || (touch {receipt}/started; nohup bash -c {shlex.quote(runner)} >/dev/null 2>&1 </dev/null &)')}"
        started = await self.sandbox.execute(launch)
        if started.exit_code:
            raise RuntimeError(started.stderr)
        offsets = {"stdout": 0, "stderr": 0}
        captured = {"stdout": "", "stderr": ""}
        while True:
            # Read both streams and exit in one command; JSON keeps arbitrary log content safe.
            reader = (
                "import json,pathlib; p=pathlib.Path("
                + repr(receipt)
                + "); print(json.dumps({k:(p/k).read_text(errors='replace') if (p/k).exists() else None for k in ['stdout','stderr','exit']}))"
            )
            poll = await self.sandbox.execute(f"python3 -c {shlex.quote(reader)}")
            if poll.exit_code:
                raise RuntimeError(poll.stderr)
            state = json.loads(poll.stdout)
            for stream in offsets:
                text = state[stream] or ""
                chunk = text[offsets[stream] :]
                if chunk:
                    await self.output(stream, chunk)
                    offsets[stream] = len(text)
                captured[stream] = text
            if state["exit"] is not None:
                return CommandResult(exit_code=int(state["exit"]), **captured)
            await asyncio.sleep(0.15)


@dataclass(kw_only=True)
class AgentWorkspace(AbstractCapability):
    """Supply the harness with a remote workspace, never the Python host."""

    backend: SandboxWorkspace
    id: str | None = "gitedge_workspace"

    @override
    def get_workspace(self, ctx: RunContext, *, ref: WorkspaceRef | None) -> WorkspaceBackend | None:
        return self.backend if ref is None or ref == self.backend.ref else None
