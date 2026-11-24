"""Static OpenCode model registry and routing metadata."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, TypeAlias, cast

__all__ = [
    "GO_MODELS",
    "MODEL_REGISTRIES",
    "SERVICE_NAMES",
    "ZEN_MODELS",
    "ModelInfo",
    "ServiceName",
    "WireFormat",
    "list_model_info",
    "list_models",
    "model_info",
    "split_model_id",
]

ServiceName: TypeAlias = Literal["opencode", "opencode-go"]
WireFormat: TypeAlias = Literal["responses", "messages", "chat", "google"]

SERVICE_NAMES: tuple[ServiceName, ServiceName] = ("opencode", "opencode-go")


@dataclass(frozen=True, slots=True)
class ModelInfo:
    """Routing metadata for an OpenCode model id."""

    id: str
    service: ServiceName
    name: str
    wire: WireFormat


# Synced from the public inference catalogs on 2026-11-24. Only chat models belong
# in a coding agent; Gemini also exposes generate-content alongside interactions.
_ZEN_MODELS: dict[str, WireFormat] = {
    "beam-free": "chat",
    "big-pickle": "chat",
    "claude-fable-5": "messages",
    "claude-fable-5-1": "messages",
    "claude-fable-5-2": "messages",
    "claude-haiku-4-5": "messages",
    "claude-haiku-5-5": "messages",
    "claude-opus-4-5": "messages",
    "claude-opus-4-6": "messages",
    "claude-opus-4-7": "messages",
    "claude-opus-4-8": "messages",
    "claude-opus-5": "messages",
    "claude-opus-5-5": "messages",
    "claude-sonnet-4-5": "messages",
    "claude-sonnet-4-6": "messages",
    "claude-sonnet-5": "messages",
    "claude-sonnet-5-5": "messages",
    "deepseek-v4-pro": "chat",
    "deepseek-v4.1-flash": "chat",
    "deepseek-v4.1-flash-free": "chat",
    "flint-40b-free": "chat",
    "gemini-3.5-flash": "google",
    "gemini-3.5-flash-lite": "google",
    "gemini-3.6-flash": "google",
    "gemini-3.7-flash": "google",
    "gemini-3.8-flash": "google",
    "gemini-4-argon": "google",
    "gemini-4-carbon": "google",
    "gemini-4-hydrogen": "google",
    "gemini-4-neon": "google",
    "glm-5.3": "chat",
    "glm-5.3-flash": "chat",
    "gpt-5": "responses",
    "gpt-5-codex": "responses",
    "gpt-5-nano": "responses",
    "gpt-5.1": "responses",
    "gpt-5.1-codex": "responses",
    "gpt-5.1-codex-max": "responses",
    "gpt-5.1-codex-mini": "responses",
    "gpt-5.2": "responses",
    "gpt-5.2-codex": "responses",
    "gpt-5.3-codex": "responses",
    "gpt-5.3-codex-spark": "responses",
    "gpt-5.4": "responses",
    "gpt-5.4-mini": "responses",
    "gpt-5.4-nano": "responses",
    "gpt-5.4-pro": "responses",
    "gpt-5.5": "responses",
    "gpt-5.5-pro": "responses",
    "gpt-5.6-luna": "responses",
    "gpt-5.6-sol": "responses",
    "gpt-5.6-terra": "responses",
    "gpt-6-astra": "responses",
    "gpt-6-luna": "responses",
    "gpt-6-sol": "responses",
    "gpt-6.1-sol": "responses",
    "gpt-6.2-astra": "responses",
    "gpt-6.2-sol": "responses",
    "grok-4.5": "responses",
    "grok-4.6": "responses",
    "grok-4.7": "responses",
    "grok-build-0.1": "responses",
    "hy4-flash-free": "chat",
    "iceman-free": "chat",
    "kimi-k2.7-code": "chat",
    "kimi-k3": "chat",
    "kimi-k3.1-pro": "chat",
    "mimo-v2.6-flash-free": "chat",
    "minimax-m2.5": "chat",
    "minimax-m2.7": "chat",
    "minimax-m3": "chat",
    "mistral-large-4": "chat",
    "muse-ember-1.0": "responses",
    "muse-spark-1.2": "responses",
    "muse-spark-1.3": "responses",
    "muse-wonder-1.0": "responses",
    "nemotron-3.5-lightning-free": "chat",
    "nemotron-3.5-super-vl-free": "chat",
    "qwen3.5-plus": "messages",
    "qwen3.6-plus": "messages",
    "qwen3.8-flash": "messages",
    "qwen3.8-max": "chat",
    "tidepool-alpha-free": "chat",
}

ZEN_MODELS: Mapping[str, WireFormat] = MappingProxyType(_ZEN_MODELS)

_GO_MODELS: dict[str, WireFormat] = {
    "beam-free": "chat",
    "claude-haiku-5-5": "messages",
    "deepseek-v4-pro": "chat",
    "deepseek-v4.1-flash": "chat",
    "gemini-4-argon": "google",
    "glm-5.3": "chat",
    "glm-5.3-flash": "chat",
    "gpt-5.6-luna": "responses",
    "gpt-6-luna": "responses",
    "grok-4.7": "responses",
    "hungerg-free": "chat",
    "hy3": "chat",
    "hy4": "chat",
    "hy4-flash-free": "chat",
    "hy4-preview": "chat",
    "iceman-contributor-free": "chat",
    "kimi-k2.7-code": "chat",
    "kimi-k3": "chat",
    "kimi-k3.1-pro": "chat",
    "longcat-2.5": "chat",
    "mimo-v2.6-flash": "chat",
    "mimo-v2.6-pro": "chat",
    "minimax-m3": "messages",
    "minimax-m3.1-flash": "chat",
    "muse-spark-1.2-contributor": "responses",
    "muse-spark-1.3-contributor": "responses",
    "qwen3.7-plus": "messages",
    "qwen3.8-flash": "messages",
    "qwen3.8-max": "messages",
    "qwen4-max": "messages",
    "step-5-preview": "chat",
}

GO_MODELS: Mapping[str, WireFormat] = MappingProxyType(_GO_MODELS)

MODEL_REGISTRIES: Mapping[ServiceName, Mapping[str, WireFormat]] = MappingProxyType(
    {
        "opencode": ZEN_MODELS,
        "opencode-go": GO_MODELS,
    }
)


def _validate_service(service: str) -> ServiceName:
    if service not in MODEL_REGISTRIES:
        raise ValueError("Unknown OpenCode service. Use 'opencode' or 'opencode-go'.")
    return cast(ServiceName, service)


def split_model_id(model_id: str) -> tuple[ServiceName, str]:
    """Split and validate an OpenCode model id into service and model name."""
    if "/" not in model_id:
        raise ValueError(
            f"Expected 'service/model', got {model_id!r}. Try 'opencode/gpt-5.5' or 'opencode-go/glm-5.1'."
        )

    service, name = model_id.split("/", 1)
    service = _validate_service(service)
    if not name:
        raise ValueError(f"Expected a model name after the service in {model_id!r}.")
    return service, name


def model_info(model_id: str) -> ModelInfo:
    """Return routing metadata for a known OpenCode model id."""
    service, name = split_model_id(model_id)
    registry = MODEL_REGISTRIES[service]
    wire = registry.get(name)
    if wire is None:
        known = ", ".join(f"{service}/{model}" for model in registry)
        raise ValueError(f"Unknown model {name!r} for service {service!r}. Known models: {known}.")
    return ModelInfo(id=f"{service}/{name}", service=service, name=name, wire=wire)


def list_model_info(
    service: str | None = None,
    *,
    wire: WireFormat | None = None,
) -> list[ModelInfo]:
    """Return routing metadata for known models, optionally filtered."""
    services = SERVICE_NAMES if service is None else (_validate_service(service),)
    models: list[ModelInfo] = []

    for service_name in services:
        for name, model_wire in MODEL_REGISTRIES[service_name].items():
            if wire is None or model_wire == wire:
                models.append(
                    ModelInfo(
                        id=f"{service_name}/{name}",
                        service=service_name,
                        name=name,
                        wire=model_wire,
                    )
                )

    return models


def list_models(
    service: str | None = None,
    *,
    wire: WireFormat | None = None,
) -> list[str]:
    """Return known OpenCode model ids, optionally filtered by service or wire."""
    return [model.id for model in list_model_info(service, wire=wire)]
