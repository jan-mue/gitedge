"""Pinned testcontainers for the real agent execution stack."""

import os

from restate.harness import RestateContainer
from testcontainers.community.k3s import K3SContainer
from testcontainers.community.ollama import OllamaContainer

# renovate: datasource=docker depName=rancher/k3s
K3S_IMAGE = "rancher/k3s:v1.35.0-k3s1"
# renovate: datasource=docker depName=ollama/ollama
OLLAMA_IMAGE = "ollama/ollama:0.18.0"
# renovate: datasource=docker depName=restatedev/restate
RESTATE_IMAGE = "restatedev/restate:1.7.2"
# renovate: datasource=github-releases depName=kubernetes-sigs/agent-sandbox
AGENT_SANDBOX_VERSION = "v1.0.2"
AGENT_SANDBOX_REVISION = "993fd4aa9f576b8374b8810ef45e7305ed2dd95d"
OLLAMA_MODEL = "qwen3.5:0.8b"


class AgentK3SContainer(K3SContainer):
    """Dedicated privileged Kubernetes cluster for SDK integration tests."""

    def __init__(self) -> None:
        super().__init__(image=K3S_IMAGE)
        self.with_exposed_ports(30080)


def ollama_container() -> OllamaContainer:
    """Return a CPU-compatible, version-pinned model server."""
    return OllamaContainer(image=OLLAMA_IMAGE)


class AgentRestateContainer(RestateContainer):
    """Route only the harness callback directly; preserve the external egress proxy."""

    def __init__(self, image: str, always_replay: bool, disable_retries: bool) -> None:
        super().__init__(image, always_replay, disable_retries)
        local = ",".join(
            filter(None, [os.environ.get("NO_PROXY", ""), "host.docker.internal", "127.0.0.1", "localhost"])
        )
        self.with_env("NO_PROXY", local)
        self.with_env("no_proxy", local)
