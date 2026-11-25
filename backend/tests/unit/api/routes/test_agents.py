from typing import TYPE_CHECKING

from app._vendor.pydantic_ai_opencode.registry import GO_MODELS, ZEN_MODELS
from app.config import settings

if TYPE_CHECKING:
    import pytest
    from fastapi.testclient import TestClient


def test_provider_discovery_includes_native_opencode_and_deduplicates_endpoints(
    client: TestClient, superuser_token_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        settings,
        "AGENTS_OPENAI_ENDPOINTS",
        {"opencode-zen": "https://models.example.test/v1", "ollama": "https://ollama.example.test/v1"},
    )
    response = client.get(f"{settings.API_V1_STR}/agents/providers", headers=superuser_token_headers)
    assert response.status_code == 200
    providers = response.json()
    identifiers = [provider["provider"] for provider in providers]
    assert identifiers.count("opencode-zen") == 1
    assert identifiers.count("opencode-go") == 1
    assert "ollama" in identifiers
    assert next(provider for provider in providers if provider["provider"] == "opencode-zen") == {
        "provider": "opencode-zen",
        "label": "OpenCode Zen",
        "auth": "key",
    }


def test_model_discovery_lists_every_current_opencode_chat_model(
    client: TestClient, superuser_token_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "AGENTS_MODELS", ["ollama:local", "opencode-go:glm-5.3"])
    response = client.get(f"{settings.API_V1_STR}/agents/models", headers=superuser_token_headers)
    assert response.status_code == 200
    models = response.json()
    assert models[0] == "ollama:local"
    assert models.count("opencode-go:glm-5.3") == 1
    assert {model.removeprefix("opencode-zen:") for model in models if model.startswith("opencode-zen:")} == set(
        ZEN_MODELS
    )
    assert {model.removeprefix("opencode-go:") for model in models if model.startswith("opencode-go:")} == set(
        GO_MODELS
    )
    assert len(ZEN_MODELS) == 83
    assert len(GO_MODELS) == 31
    assert "opencode-go:minimax-m2.7" not in models
    assert "opencode-zen:gemini-3.1-pro" not in models
