"""Container fixtures for agent runtime tests independent of the forge server."""

from typing import TYPE_CHECKING

import pytest

from tests.integration.agents.containers import OLLAMA_MODEL, AgentK3SContainer, ollama_container

if TYPE_CHECKING:
    from collections.abc import Generator

    from testcontainers.community.ollama import OllamaContainer


@pytest.fixture(autouse=True)
def _clean_repositories() -> None:
    """Agent SDK tests do not need the forge's unrelated database fixtures."""


@pytest.fixture(scope="session")
def agent_k3s() -> Generator[AgentK3SContainer]:

    with AgentK3SContainer() as cluster:
        yield cluster


@pytest.fixture(scope="session")
def agent_ollama() -> Generator[OllamaContainer]:

    with ollama_container() as container:
        container.pull_model(OLLAMA_MODEL)
        assert any(model["model"].startswith("qwen3.5:0.8b") for model in container.list_models())
        yield container
