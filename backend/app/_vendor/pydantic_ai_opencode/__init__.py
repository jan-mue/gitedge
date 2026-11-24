"""Pydantic AI integration for OpenCode Zen and OpenCode Go."""

from __future__ import annotations

from app._vendor.pydantic_ai_opencode.auth import OpenCodeAuthError, get_opencode_api_key
from app._vendor.pydantic_ai_opencode.models import opencode_model
from app._vendor.pydantic_ai_opencode.providers import (
    GO_BASE_URL,
    ZEN_BASE_URL,
    OpenCodeGoAnthropicProvider,
    OpenCodeGoGoogleProvider,
    OpenCodeGoProvider,
    OpenCodeZenAnthropicProvider,
    OpenCodeZenGoogleProvider,
    OpenCodeZenProvider,
)
from app._vendor.pydantic_ai_opencode.registry import (
    GO_MODELS,
    ZEN_MODELS,
    ModelInfo,
    ServiceName,
    WireFormat,
    list_model_info,
    list_models,
    model_info,
)

__all__ = [
    "GO_BASE_URL",
    "GO_MODELS",
    "ZEN_BASE_URL",
    "ZEN_MODELS",
    "ModelInfo",
    "OpenCodeAuthError",
    "OpenCodeGoAnthropicProvider",
    "OpenCodeGoGoogleProvider",
    "OpenCodeGoProvider",
    "OpenCodeZenAnthropicProvider",
    "OpenCodeZenGoogleProvider",
    "OpenCodeZenProvider",
    "ServiceName",
    "WireFormat",
    "__version__",
    "get_opencode_api_key",
    "list_model_info",
    "list_models",
    "model_info",
    "opencode_model",
]

__version__ = "0.2.0"
