"""Provider routing for native PydanticAI and OpenAI-compatible services."""

import os

from pydantic_ai.models import Model, infer_model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.config import settings


def resolve_model(identifier: str) -> Model:
    """Resolve server-configured providers without accepting browser-supplied URLs.

    Native identifiers include openai-chatgpt for subscription OAuth. Compatible
    endpoints, including OpenCode Go/Zen, are configured by administrators with
    credentials in GITEDGE_<PROVIDER>_API_KEY, never passed into a sandbox.
    """
    provider, _, model = identifier.partition(":")
    if provider in settings.AGENTS_OPENAI_ENDPOINTS:
        key = os.environ[f"GITEDGE_{provider.upper().replace('-', '_')}_API_KEY"]
        return OpenAIChatModel(
            model, provider=OpenAIProvider(base_url=settings.AGENTS_OPENAI_ENDPOINTS[provider], api_key=key)
        )
    return infer_model(identifier)
