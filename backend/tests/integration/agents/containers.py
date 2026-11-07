"""Pinned testcontainers for the real agent execution stack."""

from testcontainers.community.k3s import K3SContainer
from testcontainers.community.ollama import OllamaContainer

# renovate: datasource=docker depName=rancher/k3s
K3S_IMAGE = "rancher/k3s:v1.35.0-k3s1"
# renovate: datasource=docker depName=ollama/ollama
OLLAMA_IMAGE = "ollama/ollama:0.18.0"
# renovate: datasource=docker depName=restatedev/restate
RESTATE_IMAGE = "restatedev/restate:1.7.2"
OLLAMA_MODEL = "qwen3.5:0.8b"


class AgentK3SContainer(K3SContainer):
    """Dedicated privileged Kubernetes cluster for SDK integration tests."""

    def __init__(self) -> None:
        super().__init__(image=K3S_IMAGE)


def ollama_container() -> OllamaContainer:
    """Return a CPU-compatible, version-pinned model server."""
    return OllamaContainer(image=OLLAMA_IMAGE)
