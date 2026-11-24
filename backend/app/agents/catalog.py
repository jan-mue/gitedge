"""Public OpenCode chat identifiers shared by discovery and execution."""

from app._vendor.pydantic_ai_opencode.registry import MODEL_REGISTRIES, ServiceName
from app.config import settings

OPENCODE_SERVICES: dict[str, ServiceName] = {"opencode-zen": "opencode", "opencode-go": "opencode-go"}


def available_models() -> list[str]:
    """List administrator-configured models and the current OpenCode chat catalogs."""
    opencode = [
        f"{provider}:{name}" for provider, service in OPENCODE_SERVICES.items() for name in MODEL_REGISTRIES[service]
    ]
    return list(dict.fromkeys([*settings.AGENTS_MODELS, *opencode]))
