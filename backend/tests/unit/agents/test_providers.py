import json
import uuid
from typing import TYPE_CHECKING

import httpx2
import pytest
from pydantic_ai import Agent
from pydantic_ai.exceptions import UserError
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel
from pydantic_ai.providers.ollama import OllamaProvider
from sqlalchemy.ext.asyncio import AsyncSession

from app._vendor.pydantic_ai_opencode import list_model_info, opencode_model
from app._vendor.pydantic_ai_opencode.providers import (
    GO_ANTHROPIC_BASE_URL,
    GO_BASE_URL,
    GO_GOOGLE_BASE_URL,
    ZEN_ANTHROPIC_BASE_URL,
    ZEN_BASE_URL,
    ZEN_GOOGLE_BASE_URL,
    OpenCodeGoProvider,
    OpenCodeZenProvider,
)
from app.agents import providers as agent_providers
from app.agents.providers import account_model, resolve_model
from app.clients.agent_credentials import AgentCredentialStore
from app.config import settings
from app.entities.agents import AgentCredential

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pytest_mock import MockerFixture

    from app._vendor.pydantic_ai_opencode import ModelInfo


ROUTES = [
    ("opencode-zen", "gpt-5.5", OpenAIResponsesModel, "opencode-zen"),
    ("opencode-zen", "claude-opus-4-7", AnthropicModel, "opencode-zen-anthropic"),
    ("opencode-zen", "gemini-4-argon", GoogleModel, "opencode-zen-google"),
    ("opencode-zen", "glm-5.3", OpenAIChatModel, "opencode-zen"),
    ("opencode-go", "glm-5.3", OpenAIChatModel, "opencode-go"),
    ("opencode-go", "minimax-m3", AnthropicModel, "opencode-go-anthropic"),
    ("opencode-go", "gpt-6-luna", OpenAIResponsesModel, "opencode-go"),
    ("opencode-go", "gemini-4-argon", GoogleModel, "opencode-go-google"),
]


@pytest.mark.parametrize(("provider", "name", "model_type", "system"), ROUTES)
def test_opencode_routes_use_native_models_and_configured_endpoints(
    monkeypatch: pytest.MonkeyPatch, provider: str, name: str, model_type: type[Model], system: str
) -> None:
    endpoint = "https://models.example.test/v1"
    monkeypatch.setattr(settings, "AGENTS_OPENAI_ENDPOINTS", {provider: endpoint})
    monkeypatch.setenv(f"GITEDGE_{provider.upper().replace('-', '_')}_API_KEY", "server-key")
    model = resolve_model(f"{provider}:{name}", session_id="conversation-1")
    assert isinstance(model, model_type)
    assert model.model_name == name
    assert model.system == system
    assert model.base_url is not None
    assert model.base_url.rstrip("/") == endpoint
    assert model.settings is not None
    assert model.settings["extra_headers"] == {"User-Agent": "GitEdge/0.1.0", "x-opencode-session": "conversation-1"}


@pytest.mark.parametrize("info", list_model_info(), ids=lambda info: info.id)
def test_every_bundled_opencode_model_can_be_constructed(info: ModelInfo) -> None:
    # The registry supplies the exact model type; no network request or simulated model is needed.
    from_types = {
        "responses": OpenAIResponsesModel,
        "chat": OpenAIChatModel,
        "messages": AnthropicModel,
        "google": GoogleModel,
    }
    model = opencode_model(info.id, api_key="test-key")
    assert isinstance(model, from_types[info.wire])
    assert model.model_name == info.name
    endpoints = {
        ("opencode", "responses"): ZEN_BASE_URL,
        ("opencode", "chat"): ZEN_BASE_URL,
        ("opencode", "messages"): ZEN_ANTHROPIC_BASE_URL,
        ("opencode", "google"): ZEN_GOOGLE_BASE_URL,
        ("opencode-go", "responses"): GO_BASE_URL,
        ("opencode-go", "chat"): GO_BASE_URL,
        ("opencode-go", "messages"): GO_ANTHROPIC_BASE_URL,
        ("opencode-go", "google"): GO_GOOGLE_BASE_URL,
    }
    assert model.base_url is not None
    assert model.base_url.rstrip("/") == endpoints[info.service, info.wire]


@pytest.mark.parametrize("provider", ["opencode-zen", "opencode-go"])
@pytest.mark.parametrize("key", [None, ""])
def test_opencode_never_falls_back_to_shared_cli_or_environment_credentials(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture, provider: str, key: str | None
) -> None:
    variable = f"GITEDGE_{provider.upper().replace('-', '_')}_API_KEY"
    monkeypatch.delenv(variable, raising=False)
    if key is not None:
        monkeypatch.setenv(variable, key)
    monkeypatch.setenv("OPENCODE_API_KEY", "unrelated-local-key")
    read_auth = mocker.patch("app._vendor.pydantic_ai_opencode.auth.read_opencode_auth_file")
    with pytest.raises(UserError, match="OpenCode API key is required"):
        resolve_model(f"{provider}:glm-5.3")
    read_auth.assert_not_called()


@pytest.mark.parametrize(("provider", "name", "model_type", "system"), ROUTES)
@pytest.mark.parametrize("connected", [True, False])
async def test_account_opencode_models_use_owned_credentials_and_stable_session_headers(
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    provider: str,
    name: str,
    model_type: type[Model],
    system: str,
    *,
    connected: bool,
) -> None:
    user_id = uuid.uuid4()
    session_id = str(uuid.uuid4())
    monkeypatch.setenv(f"GITEDGE_{provider.upper().replace('-', '_')}_API_KEY", "server-key")
    encrypted = AgentCredentialStore.cipher(user_id, provider).encrypt(b"account-key").decode()
    db = mocker.create_autospec(AsyncSession, instance=True)
    db.__aenter__.return_value = db
    db.scalar.return_value = (
        AgentCredential(user_id=user_id, provider=provider, label="OpenCode", encrypted_secret=encrypted)
        if connected
        else None
    )
    factory = mocker.Mock(return_value=db)
    construct = mocker.spy(agent_providers, "opencode_model")
    for _turn in range(2):
        async with account_model(f"{provider}:{name}", user_id, factory, session_id=session_id) as model:
            assert isinstance(model, model_type)
            assert model.system == system
            assert model.settings is not None
            assert model.settings["extra_headers"]["x-opencode-session"] == session_id
    assert construct.call_count == 2
    assert construct.call_args.kwargs["api_key"] == ("account-key" if connected else "server-key")
    assert db.commit.await_count == (2 if connected else 0)


@pytest.mark.parametrize("provider_type", [OpenCodeZenProvider, OpenCodeGoProvider])
def test_opencode_chat_profile_retains_gateway_capability_limits(
    provider_type: type[OpenCodeZenProvider | OpenCodeGoProvider],
) -> None:
    profile = provider_type.model_profile("glm-5.3")
    assert profile is not None
    assert profile.get("openai_supports_strict_tool_definition") is False
    assert profile["supports_forced_tool_choice"] is False


def test_ollama_still_uses_its_native_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AGENTS_OPENAI_ENDPOINTS", {"ollama": "https://ollama.example.test/v1"})
    model = resolve_model("ollama:qwen3.5:0.8b")
    assert isinstance(model.provider, OllamaProvider)
    assert model.model_name == "qwen3.5:0.8b"


@pytest.mark.parametrize(("provider", "name", "model_type", "system"), ROUTES)
async def test_opencode_request_uses_native_wire_path_and_forwards_session_headers(
    provider: str, name: str, model_type: type[Model], system: str
) -> None:
    del model_type, system
    service = "opencode" if provider == "opencode-zen" else "opencode-go"
    requests: list[httpx2.Request] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        if request.url.path.endswith("/responses"):
            body = {
                "id": "resp_test",
                "object": "response",
                "created_at": 1,
                "status": "completed",
                "model": name,
                "output": [
                    {
                        "id": "msg_test",
                        "type": "message",
                        "status": "completed",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "Ready", "annotations": []}],
                    }
                ],
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }
        elif request.url.path.endswith("/messages"):
            body = {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": name,
                "content": [{"type": "text", "text": "Ready"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
            if json.loads(request.content).get("stream"):
                events = [
                    {"type": "message_start", "message": {**body, "content": [], "stop_reason": None}},
                    {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
                    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Ready"}},
                    {"type": "content_block_stop", "index": 0},
                    {
                        "type": "message_delta",
                        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                        "usage": {"output_tokens": 1},
                    },
                    {"type": "message_stop"},
                ]
                content = "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events)
                return httpx2.Response(200, text=content, headers={"content-type": "text/event-stream"})
        elif ":generateContent" in request.url.path:
            body = {
                "candidates": [
                    {"content": {"parts": [{"text": "Ready"}], "role": "model"}, "finishReason": "STOP", "index": 0}
                ],
                "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1, "totalTokenCount": 2},
            }
        else:
            body = {
                "id": "chat_test",
                "object": "chat.completion",
                "created": 1,
                "model": name,
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": "Ready"}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
        return httpx2.Response(200, json=body)

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond), timeout=1200) as client:
        model = opencode_model(
            f"{service}/{name}",
            api_key="test-key",
            http_client=client,
            settings={"extra_headers": {"User-Agent": "GitEdge/0.1.0", "x-opencode-session": "test-session"}},
        )
        result = await Agent(model).run("Say ready.")
    assert result.output == "Ready"
    assert len(requests) == 1
    request = requests[0]
    assert request.headers["x-opencode-session"] == "test-session"
    assert "GitEdge/0.1.0" in request.headers["user-agent"]
    assert "test-key" in (request.headers.get("authorization") or request.headers["x-goog-api-key"])
    assert model.base_url is not None
    suffix = (
        "/responses"
        if isinstance(model, OpenAIResponsesModel)
        else "/v1/messages"
        if isinstance(model, AnthropicModel)
        else f"/v1beta/models/{name}:generateContent"
        if isinstance(model, GoogleModel)
        else "/chat/completions"
    )
    assert str(request.url).split("?")[0] == model.base_url.rstrip("/") + suffix
