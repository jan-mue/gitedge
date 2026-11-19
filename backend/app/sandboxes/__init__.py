"""Provider workspaces using PydanticAI's standard interfaces."""

import math
import re
import shlex
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pydantic_ai.workspaces import WorkspaceCommand


def shell_command(command: WorkspaceCommand, *, shell: bool, env: Mapping[str, str] | None) -> str:
    """Quote argv and explicit environment values for provider shell APIs."""
    if isinstance(command, str) != shell:
        raise TypeError("String commands require shell=True; argv commands require shell=False")
    if not isinstance(command, str) and not command:
        raise ValueError("Command argv must not be empty")
    environment = env or {}
    if any(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) is None for key in environment):
        raise ValueError("Invalid environment variable name")
    script = command if isinstance(command, str) else shlex.join(command)
    assignments = shlex.join([f"{key}={value}" for key, value in environment.items()])
    return f"cd /workspace && exec env {assignments} /bin/sh -c {shlex.quote(script)} </dev/null"


def validate_timeout(timeout: float | None) -> None:
    """Reject invalid command deadlines before contacting a provider."""
    if timeout is not None and (not math.isfinite(timeout) or timeout <= 0):
        raise ValueError("Timeout must be a positive finite number or None")
