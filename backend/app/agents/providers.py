"""Provider routing for native PydanticAI and OpenAI-compatible services."""

import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from pydantic_ai.models import Model, infer_model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.openai_chatgpt import OpenAIChatGPTProvider

from app.clients.agent_credentials import AgentCredentialStore, ChatGPTCredentialSource
from app.config import settings

if TYPE_CHECKING:
    import uuid
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def resolve_model(identifier: str) -> Model:
    """Resolve server-configured providers without accepting browser-supplied URLs.

    Native identifiers include openai-chatgpt for subscription OAuth. Compatible
    endpoints, including OpenCode Go/Zen, are configured by administrators with
    credentials in GITEDGE_<PROVIDER>_API_KEY, never passed into a sandbox.
    """
    provider, _, model = identifier.partition(":")
    if provider == "ollama":
        return OllamaModel(
            model,
            provider=OllamaProvider(
                base_url=settings.AGENTS_OPENAI_ENDPOINTS.get(provider),
                api_key=os.environ.get("GITEDGE_OLLAMA_API_KEY"),
            ),
        )
    if provider in settings.AGENTS_OPENAI_ENDPOINTS:
        key = os.environ[f"GITEDGE_{provider.upper().replace('-', '_')}_API_KEY"]
        return OpenAIChatModel(
            model, provider=OpenAIProvider(base_url=settings.AGENTS_OPENAI_ENDPOINTS[provider], api_key=key)
        )
    return infer_model(identifier)


@asynccontextmanager
async def account_model(
    identifier: str, user_id: uuid.UUID, session_factory: async_sessionmaker[AsyncSession]
) -> AsyncGenerator[Model]:
    """Resolve fresh credentials outside the execution journal and serialize OAuth rotation."""
    provider, _, name = identifier.partition(":")
    async with session_factory() as db:
        store = AgentCredentialStore(db)
        connection = await store.connection(user_id, provider, lock=False)
        if connection is None:
            yield resolve_model(identifier)
            return
        if provider == "openai-chatgpt":
            model = OpenAIResponsesModel(
                name, provider=OpenAIChatGPTProvider(credential_source=ChatGPTCredentialSource(store, connection))
            )
        elif provider == "anthropic":
            model = AnthropicModel(name, provider=AnthropicProvider(api_key=store.decrypt(connection)))
        elif provider == "ollama":
            model = OllamaModel(
                name,
                provider=OllamaProvider(
                    base_url=settings.AGENTS_OPENAI_ENDPOINTS.get(provider), api_key=store.decrypt(connection)
                ),
            )
        else:
            base_url = settings.AGENTS_OPENAI_ENDPOINTS.get(provider, "https://api.openai.com/v1")
            transport = OpenAIProvider(base_url=base_url, api_key=store.decrypt(connection))
            model = (
                OpenAIResponsesModel(name, provider=transport)
                if provider == "openai"
                else OpenAIChatModel(name, provider=transport)
            )
        try:
            yield model
        finally:
            # The row lock spans token refresh, including an interrupted run.
            await db.commit()
