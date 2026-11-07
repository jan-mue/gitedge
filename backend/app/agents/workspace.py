"""Harness workspace with reattachable command execution in a remote sandbox."""

import asyncio
import base64
import codecs
import hashlib
import json
import shlex
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from pydantic_ai._run_context import get_current_run_context
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.workspaces import CommandResult, WorkspaceBackend, WorkspaceCommand, WorkspaceRef

from app.clients.agent_streams import AgentRunCancelledError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

    from pydantic_ai import RunContext

    from app.clients.sandbox import OutputSink, SandboxClient

CAPTURE_LIMIT = 1_000_000
READ_SIZE = 65536


class SandboxWorkspace:
    """Execute commands once, replay line events, and bound model-visible output."""

    def __init__(
        self,
        sandbox: SandboxClient,
        name: str,
        output: OutputSink,
        cancelled: Callable[[], Awaitable[bool]] | None = None,
    ) -> None:
        """Bind one run's machine and persist-before-send output callback."""
        self.sandbox, self.name, self.output = sandbox, name, output
        self.cancelled = cancelled
        self.sequence = 0

    @property
    def ref(self) -> WorkspaceRef:
        """Use the session reference, so model history never redirects tool execution."""
        return WorkspaceRef(provider="gitedge", id=self.name)

    async def working_dir(self) -> str:
        """Place repository collections below this isolated directory."""
        return "/workspace"

    async def run(
        self,
        command: WorkspaceCommand,
        *,
        shell: bool = False,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,  # noqa: ASYNC109 - remote workspace deadline
    ) -> CommandResult:
        """Detach a lock-owning runner and reattach by deterministic tool/command ID."""
        if isinstance(command, str) != shell:
            raise TypeError("String commands require shell=True")
        script = command if isinstance(command, str) else shlex.join(command)
        self.sequence += 1
        context = get_current_run_context()
        call_id = context.tool_call_id if context else str(self.sequence)
        command_id = hashlib.sha256(json.dumps([call_id, script, dict(env or {})], sort_keys=True).encode()).hexdigest()
        receipt = f"/opt/gitedge/commands/{self.name}/{command_id}"
        environment = " ".join(shlex.quote(f"{key}={value}") for key, value in (env or {}).items())
        inner = (
            f"cd /workspace && env {environment} timeout --kill-after=5s {timeout or 300} bash -c {shlex.quote(script)}"
        )
        runner = f"echo $$ >{receipt}/pid; test -f {receipt}/exit && exit 0; if test -f {receipt}/started; then echo 'Command was interrupted before its receipt completed' >>{receipt}/stderr; echo 125 >{receipt}/exit; exit 0; fi; touch {receipt}/started; {inner} >{receipt}/stdout 2>{receipt}/stderr; echo $? >{receipt}/exit.tmp; mv {receipt}/exit.tmp {receipt}/exit"
        launch = f"mkdir -p {receipt} && nohup flock -n {receipt}/lock setsid bash -c {shlex.quote(runner)} >/dev/null 2>&1 </dev/null &"
        started = await self.sandbox.execute(launch)
        if started.exit_code:
            raise RuntimeError(started.stderr)
        offsets = {"stdout": 0, "stderr": 0}
        sequences = {"stdout": 0, "stderr": 0}
        decoders = {stream: codecs.getincrementaldecoder("utf-8")("replace") for stream in offsets}
        pending = dict.fromkeys(offsets, "")
        captured = dict.fromkeys(offsets, "")
        while True:
            if self.cancelled is not None and await self.cancelled():
                await self.sandbox.execute(
                    f"if test -f {receipt}/pid; then kill -TERM -- -$(cat {receipt}/pid) 2>/dev/null || true; fi; echo 130 >{receipt}/exit"
                )
                raise AgentRunCancelledError("Run stopped")
            reader = (
                "import json,pathlib,base64; p=pathlib.Path("
                + repr(receipt)
                + "); offsets="
                + repr(offsets)
                + "; result={};\nfor k,o in offsets.items():\n f=p/k\n if f.exists():\n  with f.open('rb') as r: r.seek(o); result[k]=base64.b64encode(r.read(65536)).decode()\n else: result[k]=''\nresult['exit']=(p/'exit').read_text() if (p/'exit').exists() else None\nprint(json.dumps(result))"
            )
            polled = await self.sandbox.execute(f"python3 -c {shlex.quote(reader)}")
            if polled.exit_code:
                raise RuntimeError(polled.stderr)
            state = json.loads(polled.stdout)
            more = False
            for stream in offsets:
                raw = base64.b64decode(state[stream])
                offsets[stream] += len(raw)
                more |= len(raw) == READ_SIZE
                text = decoders[stream].decode(raw)
                captured[stream] = (captured[stream] + text)[:CAPTURE_LIMIT]
                pending[stream] += text
                while "\n" in pending[stream]:
                    line, pending[stream] = pending[stream].split("\n", 1)
                    await self.output(stream, line + "\n", command_id, sequences[stream])
                    sequences[stream] += 1
                # Avoid unbounded buffers for programs producing huge lines.
                if len(pending[stream]) > READ_SIZE:
                    await self.output(stream, pending[stream][:READ_SIZE], command_id, sequences[stream])
                    pending[stream] = pending[stream][READ_SIZE:]
                    sequences[stream] += 1
            if state["exit"] is not None and not more:
                for stream in pending:
                    pending[stream] += decoders[stream].decode(b"", final=True)
                    if pending[stream]:
                        await self.output(stream, pending[stream], command_id, sequences[stream])
                    if len(captured[stream]) == CAPTURE_LIMIT:
                        captured[stream] += "\n[Output truncated; full output is in the command log.]"
                return CommandResult(exit_code=int(state["exit"]), **captured)
            await asyncio.sleep(0.15)


@dataclass(kw_only=True)
class AgentWorkspace(AbstractCapability):
    """Supply the harness with a remote workspace, never the Python host."""

    backend: SandboxWorkspace
    id: str | None = "gitedge_workspace"

    @override
    def get_workspace(self, ctx: RunContext, *, ref: WorkspaceRef | None) -> WorkspaceBackend | None:
        # A new turn resumes the same session filesystem but uses fresh command IDs.
        return self.backend if ref is None or ref.provider == "gitedge" else None
