"""Container fixtures for agent runtime tests independent of the forge server."""

import os
import uuid
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.models.openai import OpenAIChatModelSettings
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai_harness.docker_sandbox import DockerSandbox, DockerSandboxBackend
from redis.asyncio import Redis
from testcontainers.minio import MinioContainer
from testcontainers.redis import RedisContainer

from app.agents.dependencies import AgentDeps, SetupAgentDeps
from app.agents.main import stop_workspace, workspace_backend
from app.clients.agent_streams import AgentStreamStore
from app.clients.blob_storage import S3Client
from tests.integration.agents.containers import OLLAMA_MODEL

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Generator
    from contextlib import AbstractAsyncContextManager

    from pydantic_ai.capabilities import AbstractCapability
    from pydantic_ai.workspaces import WorkspaceBackend
    from pydantic_ai_harness.smol_sandbox import SmolSandbox, SmolSandboxBackend
    from testcontainers.community.ollama import OllamaContainer


IS_CI = bool(os.environ.get("CI"))
SANDBOX_PROVIDERS = ["docker", *(["smol"] if IS_CI else [])]

type AgentRunResources = Callable[
    [str | None], AbstractAsyncContextManager[tuple[SetupAgentDeps, WorkspaceBackend, OllamaModel]]
]
type AgentModelResources = Callable[[str | None], AbstractAsyncContextManager[tuple[AgentDeps, OllamaModel]]]


@pytest.fixture(autouse=True)
def _clean_repositories() -> None:
    """Agent SDK tests do not need the forge's unrelated database fixtures."""


@pytest.fixture
async def agent_model(agent_ollama: OllamaContainer) -> AsyncGenerator[OllamaModel]:
    provider = OllamaProvider(base_url=f"{agent_ollama.get_endpoint()}/v1", api_key="ollama")
    try:
        yield OllamaModel(
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


def _docker_sandbox() -> DockerSandbox:
    return DockerSandbox(image="node:22.18.0-bookworm", allow_internet_access=False)


def _smol_sandbox() -> SmolSandbox:
    smol = pytest.importorskip("smol")
    available, _code, reason = smol.local_availability()
    if not available:
        pytest.skip(reason or "Local virtualization is unavailable")
    sandbox_module = pytest.importorskip("pydantic_ai_harness.smol_sandbox")
    return sandbox_module.SmolSandbox(image="node:22.18.0-bookworm", memory_mb=512, allow_internet_access=False)


@pytest.fixture(params=SANDBOX_PROVIDERS)
def sandbox_provider(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def agent_sandbox_capability(sandbox_provider: str) -> AbstractCapability[SetupAgentDeps]:
    return _docker_sandbox() if sandbox_provider == "docker" else _smol_sandbox()


@pytest.fixture
def docker_sandbox_capability() -> DockerSandbox:
    return _docker_sandbox()


@pytest.fixture
def smol_sandbox_capability() -> SmolSandbox:
    if not IS_CI:
        pytest.skip("Smol integration tests run only in CI")
    return _smol_sandbox()


@pytest.fixture
async def agent_sandbox(setup_agent_deps: SetupAgentDeps) -> AsyncGenerator[WorkspaceBackend]:
    backend = await workspace_backend(setup_agent_deps, f"test-{uuid.uuid4()}")
    try:
        await backend.working_dir()
        yield backend
    finally:
        if isinstance(backend, DockerSandboxBackend) and backend.ref is not None:
            await DockerSandbox().destroy(backend.ref)
        else:
            await stop_workspace(backend)


@pytest.fixture
async def smol_sandbox(smol_sandbox_capability: SmolSandbox) -> AsyncGenerator[SmolSandboxBackend]:
    sandbox_module = pytest.importorskip("pydantic_ai_harness.smol_sandbox")
    sandbox = sandbox_module.SmolSandboxBackend(
        image=smol_sandbox_capability.image, memory_mb=smol_sandbox_capability.memory_mb
    )
    try:
        await sandbox.get_sandbox()
        yield sandbox
    finally:
        await stop_workspace(sandbox)


@pytest.fixture
def setup_agent_deps(
    agent_streams: AgentStreamStore,
    agent_blobs: S3Client,
    agent_sandbox_capability: AbstractCapability[SetupAgentDeps],
) -> SetupAgentDeps:
    return SetupAgentDeps(streams=agent_streams, blobs=agent_blobs, sandbox=agent_sandbox_capability)


@pytest.fixture
def smol_setup_agent_deps(
    agent_streams: AgentStreamStore,
    agent_blobs: S3Client,
    smol_sandbox_capability: SmolSandbox,
) -> SetupAgentDeps:
    return SetupAgentDeps(streams=agent_streams, blobs=agent_blobs, sandbox=smol_sandbox_capability)


@pytest.fixture
def docker_setup_agent_deps(
    agent_streams: AgentStreamStore,
    agent_blobs: S3Client,
    docker_sandbox_capability: DockerSandbox,
) -> SetupAgentDeps:
    return SetupAgentDeps(streams=agent_streams, blobs=agent_blobs, sandbox=docker_sandbox_capability)


@pytest.fixture
def agent_model_resources(
    agent_blobs: S3Client, agent_redis: RedisContainer, agent_ollama: OllamaContainer
) -> AgentModelResources:
    """Create network clients on the requesting loop, including the SDK harness's server loop."""

    @asynccontextmanager
    async def resources(endpoint: str | None) -> AsyncGenerator[tuple[AgentDeps, OllamaModel]]:
        url = f"redis://{agent_redis.get_container_host_ip()}:{agent_redis.get_exposed_port(6379)}/0"
        provider = OllamaProvider(base_url=endpoint or f"{agent_ollama.get_endpoint()}/v1", api_key="ollama")
        try:
            async with Redis.from_url(url, decode_responses=True) as client:
                model = OllamaModel(
                    OLLAMA_MODEL, provider=provider, settings=OpenAIChatModelSettings(openai_reasoning_effort="none")
                )
                yield AgentDeps(streams=AgentStreamStore(client), blobs=agent_blobs), model
        finally:
            await provider.client.close()

    return resources


@pytest.fixture
def agent_run_resources(
    agent_model_resources: AgentModelResources, setup_agent_deps: SetupAgentDeps, agent_sandbox: WorkspaceBackend
) -> AgentRunResources:
    """Add native compute only for tests that exercise setup or command execution."""

    @asynccontextmanager
    async def resources(
        endpoint: str | None,
    ) -> AsyncGenerator[tuple[SetupAgentDeps, WorkspaceBackend, OllamaModel]]:
        async with agent_model_resources(endpoint) as (common, model):
            yield replace(setup_agent_deps, streams=common.streams, blobs=common.blobs), agent_sandbox, model

    return resources
