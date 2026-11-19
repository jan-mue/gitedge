"""Container fixtures for agent runtime tests independent of the forge server."""

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from redis.asyncio import Redis
from testcontainers.minio import MinioContainer
from testcontainers.redis import RedisContainer

from app.agents.runtime import stop_workspace
from app.api.dependencies import get_coding_agent_deps
from app.clients.agent_streams import AgentStreamStore
from app.clients.blob_storage import S3Client
from tests.integration.agents.containers import OLLAMA_MODEL, ollama_container

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from pydantic_ai_harness.smol_sandbox import SmolSandbox, SmolSandboxBackend
    from testcontainers.community.ollama import OllamaContainer

    from app.agents.dependencies import CodingAgentDeps


@pytest.fixture(autouse=True)
def _clean_repositories() -> None:
    """Agent SDK tests do not need the forge's unrelated database fixtures."""


@pytest.fixture(scope="session")
def agent_ollama() -> Generator[OllamaContainer]:

    with ollama_container() as container:
        container.pull_model(OLLAMA_MODEL)
        assert any(model["model"].startswith("qwen3.5:0.8b") for model in container.list_models())
        yield container


@pytest.fixture
async def agent_model(agent_ollama: OllamaContainer) -> AsyncGenerator[OpenAIChatModel]:
    provider = OpenAIProvider(base_url=f"{agent_ollama.get_endpoint()}/v1", api_key="ollama")
    try:
        yield OpenAIChatModel(
            OLLAMA_MODEL, provider=provider, settings=OpenAIChatModelSettings(openai_reasoning_effort="none")
        )
    finally:
        await provider.client.close()


@pytest.fixture(scope="session")
def agent_redis() -> Generator[RedisContainer]:
    with RedisContainer("redis:8.6.0") as container:
        yield container


@pytest.fixture
async def agent_streams(agent_redis: RedisContainer) -> AsyncGenerator[AgentStreamStore]:
    url = f"redis://{agent_redis.get_container_host_ip()}:{agent_redis.get_exposed_port(6379)}/0"
    async with Redis.from_url(url, decode_responses=True) as redis:
        try:
            yield AgentStreamStore(redis)
        finally:
            await redis.flushdb()


@pytest.fixture(scope="session")
def agent_minio() -> Generator[MinioContainer]:
    with MinioContainer(
        "cgr.dev/chainguard/minio@sha256:9dcc028b309030afa86fc1fc8d93907ae373ea3fb75277cca3fc77e4645932b7"
    ) as container:
        yield container


@pytest.fixture
async def agent_blobs(agent_minio: MinioContainer) -> AsyncGenerator[S3Client]:
    blobs = S3Client(
        endpoint=f"{agent_minio.get_container_host_ip()}:{agent_minio.get_exposed_port(9000)}",
        access_key=agent_minio.access_key,
        secret_key=agent_minio.secret_key,
        bucket="gitedge-agents-test",
    )
    try:
        yield blobs
    finally:
        for key in await blobs.list_keys(""):
            await blobs.delete(key)


@pytest.fixture
def agent_sandbox_capability() -> SmolSandbox:
    smol = pytest.importorskip("smol")
    available, _code, reason = smol.local_availability()
    if not available:
        pytest.skip(reason or "Local virtualization is unavailable")
    from pydantic_ai_harness.smol_sandbox import SmolSandbox  # noqa: PLC0415 - optional host virtualization

    return SmolSandbox(image="python:3.14.10-slim-bookworm", memory_mb=512)


@pytest.fixture
async def agent_sandbox(agent_sandbox_capability: SmolSandbox) -> AsyncGenerator[SmolSandboxBackend]:
    from pydantic_ai_harness.smol_sandbox import SmolSandboxBackend  # noqa: PLC0415 - optional host virtualization

    sandbox = SmolSandboxBackend(image=agent_sandbox_capability.image, memory_mb=agent_sandbox_capability.memory_mb)
    try:
        await sandbox.get_sandbox()
        yield sandbox
    finally:
        await stop_workspace(sandbox)


@pytest.fixture
def agent_coding_deps(
    agent_sandbox: SmolSandboxBackend,
    agent_streams: AgentStreamStore,
    agent_blobs: S3Client,
    agent_sandbox_capability: SmolSandbox,
) -> CodingAgentDeps:
    deps = get_coding_agent_deps(agent_streams, agent_blobs, agent_sandbox_capability)
    return replace(deps, workspace=agent_sandbox)
