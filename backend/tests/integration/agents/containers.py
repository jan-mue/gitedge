"""Pinned testcontainers for the real agent execution stack."""

import os

from restate.harness import RestateContainer
from testcontainers.community.k3s import K3SContainer
from testcontainers.community.ollama import OllamaContainer

# renovate: datasource=docker depName=rancher/k3s
K3S_IMAGE = "rancher/k3s:v1.37.2-k3s1"
# renovate: datasource=docker depName=ollama/ollama
OLLAMA_IMAGE = "ollama/ollama:0.40.16"
# renovate: datasource=docker depName=restatedev/restate
RESTATE_IMAGE = "restatedev/restate:1.8.1"
# renovate: datasource=github-releases depName=kubernetes-sigs/agent-sandbox
AGENT_SANDBOX_VERSION = "v1.0.11"
AGENT_SANDBOX_REVISION = "890de53a4dd18e35313173e6dc34d9559b1a9733"
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
