"""Pydantic AI provider classes for OpenCode."""

from __future__ import annotations

from os import PathLike
from typing import TYPE_CHECKING, overload, override

from pydantic_ai.profiles import ModelProfile, merge_profile
from pydantic_ai.profiles.openai import OpenAIModelProfile, openai_model_profile
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider

from app._vendor.pydantic_ai_opencode.auth import get_opencode_api_key
from app._vendor.pydantic_ai_opencode.registry import GO_MODELS, ZEN_MODELS

if TYPE_CHECKING:
    from google.genai import Client
    from httpx2 import AsyncClient
    from openai import AsyncOpenAI
    from pydantic_ai.providers.anthropic import AsyncAnthropicClient


__all__ = [
    "GO_BASE_URL",
    "GO_ANTHROPIC_BASE_URL",
    "GO_GOOGLE_BASE_URL",
    "ZEN_BASE_URL",
    "ZEN_ANTHROPIC_BASE_URL",
    "ZEN_GOOGLE_BASE_URL",
    "OpenCodeGoAnthropicProvider",
    "OpenCodeGoProvider",
    "OpenCodeGoGoogleProvider",
    "OpenCodeZenAnthropicProvider",
    "OpenCodeZenGoogleProvider",
    "OpenCodeZenProvider",
]

ZEN_BASE_URL = "https://opencode.ai/inference/openai/v1"
ZEN_ANTHROPIC_BASE_URL = "https://opencode.ai/inference/anthropic"
ZEN_GOOGLE_BASE_URL = "https://opencode.ai/inference/google"
GO_BASE_URL = "https://opencode.ai/inference/go/openai/v1"
GO_ANTHROPIC_BASE_URL = "https://opencode.ai/inference/go/anthropic"
GO_GOOGLE_BASE_URL = "https://opencode.ai/inference/go/google"

_OPENAI_COMPATIBLE_PROFILE = OpenAIModelProfile(
    openai_supports_strict_tool_definition=False,
    supports_forced_tool_choice=False,
)


def _opencode_openai_profile(model_name: str) -> ModelProfile | None:
    """Return a conservative profile for OpenAI-compatible OpenCode models."""
    if ZEN_MODELS.get(model_name) == "responses" or GO_MODELS.get(model_name) == "responses":
        return openai_model_profile(model_name)
    return merge_profile(openai_model_profile(model_name), _OPENAI_COMPATIBLE_PROFILE)


class OpenCodeZenProvider(OpenAIProvider):
    """OpenCode Zen provider for OpenAI Responses and Chat models."""

    @overload
    def __init__(self, *, openai_client: AsyncOpenAI) -> None: ...

    @overload
    def __init__(
        self,
        *,
        api_key: str | None = None,
        auth_file: str | PathLike[str] | None = None,
        base_url: str = ZEN_BASE_URL,
        openai_client: None = None,
        http_client: AsyncClient | None = None,
    ) -> None: ...

    def __init__(
        self,
        *,
        api_key: str | None = None,
        auth_file: str | PathLike[str] | None = None,
        base_url: str = ZEN_BASE_URL,
        openai_client: AsyncOpenAI | None = None,
        http_client: AsyncClient | None = None,
    ) -> None:
        if openai_client is not None:
            if api_key is not None or auth_file is not None or http_client is not None or base_url != ZEN_BASE_URL:
                raise ValueError("Do not pass api_key, auth_file, base_url, or http_client with openai_client.")
            super().__init__(openai_client=openai_client)
            return

        super().__init__(
            base_url=base_url,
            api_key=get_opencode_api_key(
                api_key,
                service="opencode",
                auth_file=auth_file,
            ),
            http_client=http_client,
        )

    @property
    @override
    def name(self) -> str:
        return "opencode-zen"

    @staticmethod
    @override
    def model_profile(model_name: str) -> ModelProfile | None:
        return _opencode_openai_profile(model_name)


class OpenCodeZenAnthropicProvider(AnthropicProvider):
    """OpenCode Zen provider for Anthropic Messages models."""

    @overload
    def __init__(self, *, anthropic_client: AsyncAnthropicClient) -> None: ...

    @overload
    def __init__(
        self,
        *,
        api_key: str | None = None,
        auth_file: str | PathLike[str] | None = None,
        base_url: str = ZEN_ANTHROPIC_BASE_URL,
        anthropic_client: None = None,
        http_client: AsyncClient | None = None,
    ) -> None: ...

    def __init__(
        self,
        *,
        api_key: str | None = None,
        auth_file: str | PathLike[str] | None = None,
        base_url: str = ZEN_ANTHROPIC_BASE_URL,
        anthropic_client: AsyncAnthropicClient | None = None,
        http_client: AsyncClient | None = None,
    ) -> None:
        if anthropic_client is not None:
            if (
                api_key is not None
                or auth_file is not None
                or http_client is not None
                or base_url != ZEN_ANTHROPIC_BASE_URL
            ):
                raise ValueError("Do not pass api_key, auth_file, base_url, or http_client with anthropic_client.")
            super().__init__(anthropic_client=anthropic_client)
            return

        super().__init__(
            base_url=base_url,
            api_key=get_opencode_api_key(
                api_key,
                service="opencode",
                auth_file=auth_file,
            ),
            http_client=http_client,
        )

    @property
    @override
    def name(self) -> str:
        return "opencode-zen-anthropic"


class OpenCodeZenGoogleProvider(GoogleProvider):
    """OpenCode Zen provider for Gemini generateContent models."""

    @overload
    def __init__(self, *, client: Client) -> None: ...

    @overload
    def __init__(
        self,
        *,
        api_key: str | None = None,
        auth_file: str | PathLike[str] | None = None,
        base_url: str = ZEN_GOOGLE_BASE_URL,
        client: None = None,
        http_client: AsyncClient | None = None,
    ) -> None: ...

    def __init__(
        self,
        *,
        api_key: str | None = None,
        auth_file: str | PathLike[str] | None = None,
        base_url: str = ZEN_GOOGLE_BASE_URL,
        client: Client | None = None,
        http_client: AsyncClient | None = None,
    ) -> None:
        if client is not None:
            if (
                api_key is not None
                or auth_file is not None
                or http_client is not None
                or base_url != ZEN_GOOGLE_BASE_URL
            ):
                raise ValueError("Do not pass api_key, auth_file, base_url, or http_client with client.")
            super().__init__(client=client)
            return

        super().__init__(
            api_key=get_opencode_api_key(
                api_key,
                service="opencode",
                auth_file=auth_file,
            ),
            base_url=base_url,
            http_client=http_client,
        )

    @property
    @override
    def name(self) -> str:
        return "opencode-zen-google"


class OpenCodeGoProvider(OpenAIProvider):
    """OpenCode Go provider for OpenAI-compatible Chat models."""

    @overload
    def __init__(self, *, openai_client: AsyncOpenAI) -> None: ...

    @overload
    def __init__(
        self,
        *,
        api_key: str | None = None,
        auth_file: str | PathLike[str] | None = None,
        base_url: str = GO_BASE_URL,
        openai_client: None = None,
        http_client: AsyncClient | None = None,
    ) -> None: ...

    def __init__(
        self,
        *,
        api_key: str | None = None,
        auth_file: str | PathLike[str] | None = None,
        base_url: str = GO_BASE_URL,
        openai_client: AsyncOpenAI | None = None,
        http_client: AsyncClient | None = None,
    ) -> None:
        if openai_client is not None:
            if api_key is not None or auth_file is not None or http_client is not None or base_url != GO_BASE_URL:
                raise ValueError("Do not pass api_key, auth_file, base_url, or http_client with openai_client.")
            super().__init__(openai_client=openai_client)
            return

        super().__init__(
            base_url=base_url,
            api_key=get_opencode_api_key(
                api_key,
                service="opencode-go",
                auth_file=auth_file,
            ),
            http_client=http_client,
        )

    @property
    @override
    def name(self) -> str:
        return "opencode-go"

    @staticmethod
    @override
    def model_profile(model_name: str) -> ModelProfile | None:
        return _opencode_openai_profile(model_name)


class OpenCodeGoAnthropicProvider(AnthropicProvider):
    """OpenCode Go provider for Anthropic Messages models."""

    @overload
    def __init__(self, *, anthropic_client: AsyncAnthropicClient) -> None: ...

    @overload
    def __init__(
        self,
        *,
        api_key: str | None = None,
        auth_file: str | PathLike[str] | None = None,
        base_url: str = GO_ANTHROPIC_BASE_URL,
        anthropic_client: None = None,
        http_client: AsyncClient | None = None,
    ) -> None: ...

    def __init__(
        self,
        *,
        api_key: str | None = None,
        auth_file: str | PathLike[str] | None = None,
        base_url: str = GO_ANTHROPIC_BASE_URL,
        anthropic_client: AsyncAnthropicClient | None = None,
        http_client: AsyncClient | None = None,
    ) -> None:
        if anthropic_client is not None:
            if (
                api_key is not None
                or auth_file is not None
                or http_client is not None
                or base_url != GO_ANTHROPIC_BASE_URL
            ):
                raise ValueError("Do not pass api_key, auth_file, base_url, or http_client with anthropic_client.")
            super().__init__(anthropic_client=anthropic_client)
            return

        super().__init__(
            base_url=base_url,
            api_key=get_opencode_api_key(
                api_key,
                service="opencode-go",
                auth_file=auth_file,
            ),
            http_client=http_client,
        )

    @property
    @override
    def name(self) -> str:
        return "opencode-go-anthropic"


class OpenCodeGoGoogleProvider(GoogleProvider):
    """OpenCode Go provider for Gemini generateContent models."""

    @overload
    def __init__(self, *, client: Client) -> None: ...

    @overload
    def __init__(
        self,
        *,
        api_key: str | None = None,
        auth_file: str | PathLike[str] | None = None,
        base_url: str = GO_GOOGLE_BASE_URL,
        client: None = None,
        http_client: AsyncClient | None = None,
    ) -> None: ...

    def __init__(
        self,
        *,
        api_key: str | None = None,
        auth_file: str | PathLike[str] | None = None,
        base_url: str = GO_GOOGLE_BASE_URL,
        client: Client | None = None,
        http_client: AsyncClient | None = None,
    ) -> None:
        if client is not None:
            if (
                api_key is not None
                or auth_file is not None
                or http_client is not None
                or base_url != GO_GOOGLE_BASE_URL
            ):
                raise ValueError("Do not pass api_key, auth_file, base_url, or http_client with client.")
            super().__init__(client=client)
            return
        super().__init__(
            api_key=get_opencode_api_key(api_key, service="opencode-go", auth_file=auth_file),
            base_url=base_url,
            http_client=http_client,
        )

    @property
    @override
    def name(self) -> str:
        return "opencode-go-google"
