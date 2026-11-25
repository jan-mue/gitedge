"""Authentication helpers for OpenCode API keys."""

from __future__ import annotations

import json
import os
from os import PathLike
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_OPENCODE_API_KEY_ENV_VAR",
    "OPENCODE_AUTH_FILE",
    "OPENCODE_SERVICES",
    "OpenCodeAuthError",
    "get_opencode_api_key",
    "read_opencode_auth_file",
]

DEFAULT_OPENCODE_API_KEY_ENV_VAR = "OPENCODE_API_KEY"
OPENCODE_AUTH_FILE = Path.home() / ".local" / "share" / "opencode" / "auth.json"
OPENCODE_SERVICES = ("opencode", "opencode-go")


class OpenCodeAuthError(RuntimeError):
    """Raised when no OpenCode API key can be found."""


def read_opencode_auth_file(
    auth_file: str | PathLike[str] | None = None,
) -> dict[str, Any]:
    """Read the OpenCode CLI auth file.

    Invalid or missing auth files are treated as absent so callers can fall back
    to other auth sources without handling filesystem details.
    """
    path = Path(auth_file) if auth_file is not None else OPENCODE_AUTH_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError, OSError, json.JSONDecodeError:
        return {}

    return data if isinstance(data, dict) else {}


def get_opencode_api_key(
    api_key: str | None = None,
    *,
    service: str = "opencode",
    env_var: str = DEFAULT_OPENCODE_API_KEY_ENV_VAR,
    auth_file: str | PathLike[str] | None = None,
) -> str:
    """Return an OpenCode API key from an explicit value, env var, or CLI auth.

    Args:
        api_key: Explicit API key. Takes precedence when provided.
        service: OpenCode service auth entry to read from the CLI auth file.
        env_var: Environment variable to check after `api_key`.
        auth_file: Optional path to an OpenCode CLI auth file. Defaults to the
            standard OpenCode auth location.

    Raises:
        OpenCodeAuthError: If no non-empty API key is available.
    """
    if api_key:
        return api_key

    if value := os.environ.get(env_var):
        return value

    auth_data = read_opencode_auth_file(auth_file)
    auth_services = (service, "opencode") if service == "opencode-go" else (service,)
    for auth_service in auth_services:
        entry = auth_data.get(auth_service)
        if isinstance(entry, dict):
            key = entry.get("key")
            if isinstance(key, str) and key:
                return key

    raise OpenCodeAuthError(f"No OpenCode API key found for {service!r}. Set ${env_var} or run `opencode auth login`.")
