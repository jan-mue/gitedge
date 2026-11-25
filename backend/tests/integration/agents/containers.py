"""Pinned testcontainers for the real agent execution stack."""

from testcontainers.community.ollama import OllamaContainer

# renovate: datasource=docker depName=ollama/ollama
OLLAMA_IMAGE = "ollama/ollama:0.40.16"
# renovate: datasource=docker depName=restatedev/restate
RESTATE_IMAGE = "restatedev/restate:1.8.1"
OLLAMA_MODEL = "qwen3.5:0.8b"


def ollama_container() -> OllamaContainer:
    """Return a CPU-compatible, version-pinned model server."""
    return OllamaContainer(image=OLLAMA_IMAGE).with_env("OLLAMA_CONTEXT_LENGTH", "8192")
