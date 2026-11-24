# pydantic-ai-opencode

Pydantic AI providers and a model factory for [OpenCode Zen](https://opencode.ai/docs/zen/) and [OpenCode Go](https://opencode.ai/docs/go/).

OpenCode exposes multiple model families through one gateway per service, but those families use different wire formats. This package chooses the right Pydantic AI model class and provider for each OpenCode model id.

## Install

```bash
pip install pydantic-ai-opencode
```

or from this checkout:

```bash
uv sync
```

## Authentication

Set an API key:

```bash
export OPENCODE_API_KEY="..."
```

or log in with the OpenCode CLI:

```bash
opencode auth login
```

The library checks `OPENCODE_API_KEY` first, then the matching entry in
`~/.local/share/opencode/auth.json`, for example:

```json
{
  "opencode-go": {
    "type": "api",
    "key": "..."
  }
}
```

## Quick Start

```python
from pydantic_ai import Agent
from pydantic_ai_opencode import opencode_model

agent = Agent(
    opencode_model("opencode-go/glm-5.1"),
    instructions="You are concise and helpful.",
)

result = agent.run_sync("Explain Pydantic AI in one sentence.")
print(result.output)
```

## Model Factory

Use `opencode_model()` with OpenCode model ids:

```python
from pydantic_ai_opencode import opencode_model

model = opencode_model("opencode/gpt-5.5")
model = opencode_model("opencode/claude-opus-4-7")
model = opencode_model("opencode/gemini-3.1-pro")
model = opencode_model("opencode-go/glm-5.1")
model = opencode_model("opencode-go/minimax-m2.7")
```

You can pass an explicit API key, a custom OpenCode auth file, Pydantic AI model settings, a profile override, or a shared `httpx.AsyncClient`:

```python
from httpx import AsyncClient
from pydantic_ai_opencode import opencode_model

client = AsyncClient(timeout=30)
model = opencode_model(
    "opencode-go/qwen3.6-plus",
    api_key="...",
    http_client=client,
)
```

## Direct Providers

Use provider classes directly when you need to build the Pydantic AI model yourself or provide a custom SDK client:

```python
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai_opencode import OpenCodeGoProvider

model = OpenAIChatModel(
    "glm-5.1",
    provider=OpenCodeGoProvider(api_key="..."),
)
agent = Agent(model)
```

Public providers:

- `OpenCodeZenProvider`: Zen OpenAI client for GPT Responses and chat models
- `OpenCodeZenAnthropicProvider`: Zen Anthropic client for Claude models
- `OpenCodeZenGoogleProvider`: Zen Google client for Gemini models
- `OpenCodeGoProvider`: Go OpenAI client for chat models
- `OpenCodeGoAnthropicProvider`: Go Anthropic client for MiniMax messages models

## Routing

The factory routes models according to OpenCode service and wire format:

- `opencode/gpt-*`: `OpenAIResponsesModel`
- `opencode/claude-*`: `AnthropicModel`
- `opencode/gemini-*`: `GoogleModel`
- `opencode/<chat-model>`: `OpenAIChatModel`
- `opencode-go/<chat-model>`: `OpenAIChatModel`
- `opencode-go/minimax-*`: `AnthropicModel`

List known models:

```python
from pydantic_ai_opencode import list_models

print(list_models("opencode-go"))
```

## Development

```bash
uv sync --extra dev
uv run ruff format .
uv run ruff check .
uv run ty check
uv run pytest
uv build
```
