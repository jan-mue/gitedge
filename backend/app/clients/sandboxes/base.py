"""Provider-independent sandbox lifecycle. No workflow logic belongs in adapters."""

from dataclasses import dataclass, field
from typing import Protocol


class SandboxError(RuntimeError):
    """A provider could not create, inspect, or clean up a job sandbox."""


@dataclass
class SandboxSnapshot:
    """Bounded data read from a job sandbox."""

    running: bool
    files: dict[str, bytes] = field(default_factory=dict)


class SandboxClient(Protocol):
    """Implement this contract to add another sandbox provider."""

    async def start(self, name: str, files: dict[str, bytes], lifetime: int) -> None:
        """Idempotently start one isolated job under a stable name."""
        ...

    async def inspect(self, name: str) -> SandboxSnapshot:
        """Read logs/result and portable state without resuming stopped sandboxes."""
        ...

    async def delete(self, name: str) -> None:
        """Idempotently destroy a sandbox, including any running commands."""
        ...


MAX_FILE_BYTES = 32 * 1024 * 1024
# Read the marker first: if it exists, subsequent result/state reads are complete.
READ_FILES = ("exit-code", "result.json", "log.jsonl", "state.tar.gz", "cache.tar.gz")
