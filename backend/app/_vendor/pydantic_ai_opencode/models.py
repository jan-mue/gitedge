"""Model factory for OpenCode model ids."""

from __future__ import annotations

from os import PathLike
from typing import TYPE_CHECKING

from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel
from pydantic_ai.profiles import ModelProfileSpec
from pydantic_ai.settings import ModelSettings

from app._vendor.pydantic_ai_opencode.auth import get_opencode_api_key
from app._vendor.pydantic_ai_opencode.providers import (
    GO_ANTHROPIC_BASE_URL,
    GO_BASE_URL,
    GO_GOOGLE_BASE_URL,
    ZEN_ANTHROPIC_BASE_URL,
    ZEN_BASE_URL,
    ZEN_GOOGLE_BASE_URL,
    OpenCodeGoAnthropicProvider,
    OpenCodeGoGoogleProvider,
    OpenCodeGoProvider,
    OpenCodeZenAnthropicProvider,
    OpenCodeZenGoogleProvider,
    OpenCodeZenProvider,
)
from app._vendor.pydantic_ai_opencode.registry import ModelInfo, model_info

if TYPE_CHECKING:
    from httpx2 import AsyncClient


__all__ = ["opencode_model"]


def _build_model(
    info: ModelInfo,
    *,
    api_key: str,
    base_url: str | None = None,
    http_client: AsyncClient | None = None,
    profile: ModelProfileSpec | None = None,
    settings: ModelSettings | None = None,
) -> Model:
    if info.service == "opencode":
        if info.wire == "responses":
            return OpenAIResponsesModel(
                info.name,
                provider=OpenCodeZenProvider(
                    api_key=api_key, base_url=base_url or ZEN_BASE_URL, http_client=http_client
                ),
                profile=profile,
                settings=settings,
            )
        if info.wire == "chat":
            return OpenAIChatModel(
                info.name,
                provider=OpenCodeZenProvider(
                    api_key=api_key, base_url=base_url or ZEN_BASE_URL, http_client=http_client
                ),
                profile=profile,
                settings=settings,
            )
        if info.wire == "messages":
            return AnthropicModel(
                info.name,
                provider=OpenCodeZenAnthropicProvider(
                    api_key=api_key,
                    base_url=base_url or ZEN_ANTHROPIC_BASE_URL,
                    http_client=http_client,
                ),
                profile=profile,
                settings=settings,
            )
        if info.wire == "google":
            return GoogleModel(
                info.name,
                provider=OpenCodeZenGoogleProvider(
                    api_key=api_key,
                    base_url=base_url or ZEN_GOOGLE_BASE_URL,
                    http_client=http_client,
                ),
                profile=profile,
                settings=settings,
            )

    if info.service == "opencode-go":
        if info.wire == "responses":
            return OpenAIResponsesModel(
                info.name,
                provider=OpenCodeGoProvider(api_key=api_key, base_url=base_url or GO_BASE_URL, http_client=http_client),
                profile=profile,
                settings=settings,
            )
        if info.wire == "google":
            return GoogleModel(
                info.name,
                provider=OpenCodeGoGoogleProvider(
                    api_key=api_key, base_url=base_url or GO_GOOGLE_BASE_URL, http_client=http_client
                ),
                profile=profile,
                settings=settings,
            )
        if info.wire == "chat":
            return OpenAIChatModel(
                info.name,
                provider=OpenCodeGoProvider(api_key=api_key, base_url=base_url or GO_BASE_URL, http_client=http_client),
                profile=profile,
                settings=settings,
            )
        if info.wire == "messages":
            return AnthropicModel(
                info.name,
                provider=OpenCodeGoAnthropicProvider(
                    api_key=api_key,
                    base_url=base_url or GO_ANTHROPIC_BASE_URL,
                    http_client=http_client,
                ),
                profile=profile,
                settings=settings,
            )

    raise ValueError(f"Unsupported OpenCode model route: {info!r}")


def opencode_model(
    model_id: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    auth_file: str | PathLike[str] | None = None,
    http_client: AsyncClient | None = None,
    profile: ModelProfileSpec | None = None,
    settings: ModelSettings | None = None,
) -> Model:
    """Build a Pydantic AI model from an OpenCode model id.

    Args:
        model_id: OpenCode model id, for example `opencode/gpt-5.5` or
            `opencode-go/glm-5.1`.
        api_key: Optional OpenCode API key. If omitted, `$OPENCODE_API_KEY` and
            the OpenCode CLI auth file are checked.
        auth_file: Optional OpenCode CLI auth file path.
        base_url: Optional server-managed OpenCode API base URL.
        http_client: Optional shared `httpx.AsyncClient` for requests.
        profile: Optional Pydantic AI model profile override.
        settings: Optional default Pydantic AI model settings.
    """
    info = model_info(model_id)
    resolved_api_key = get_opencode_api_key(
        api_key,
        service=info.service,
        auth_file=auth_file,
    )
    return _build_model(
        info,
        api_key=resolved_api_key,
        base_url=base_url,
        http_client=http_client,
        profile=profile,
        settings=settings,
    )
