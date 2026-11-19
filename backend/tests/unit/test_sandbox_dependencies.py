from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from vercel.sandbox import SandboxClient

from app.agents.dependencies import CODING_AGENT_DEPS
from app.api.dependencies import (
    get_agent_sandbox,
    get_agent_streams_store,
    get_blob_client,
    get_vercel_sandbox_client,
)
from app.api.restate import RestateDependencies
from app.clients.agent_streams import AgentStreamStore
from app.clients.blob_storage import BlobStorageClient
from app.sandboxes.vercel import VercelSandbox

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from pytest_mock import MockerFixture
    from starlette.types import Receive, Scope, Send


def test_provider_capabilities_use_injected_clients(mocker: MockerFixture) -> None:
    vercel = mocker.create_autospec(SandboxClient, instance=True)
    vercel_capability = get_agent_sandbox(vercel)
    assert isinstance(vercel_capability, VercelSandbox)
    assert vercel_capability.client is vercel


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_fastapi_nested_deps_live_through_mounted_restate_stream(mocker: MockerFixture, method: str) -> None:
    app = FastAPI()
    streams = mocker.create_autospec(AgentStreamStore, instance=True)
    blobs = mocker.create_autospec(BlobStorageClient, instance=True)
    vercel = mocker.create_autospec(SandboxClient, instance=True)
    lifecycle = []

    async def stream_dependency() -> AsyncGenerator[AgentStreamStore]:
        lifecycle.append("open")
        yield streams
        lifecycle.append("close")

    async def protocol_app(scope: Scope, receive: Receive, send: Send) -> None:
        deps = CODING_AGENT_DEPS.get()
        assert deps.streams is streams
        assert deps.blobs is blobs
        assert isinstance(deps.sandbox, VercelSandbox)
        assert deps.sandbox.client is vercel
        assert lifecycle == ["open"]
        assert scope["path"] == "/restate/discover"
        assert scope["root_path"] == "/restate"
        request = await receive()
        assert request["body"] == b"opaque protocol bytes"
        await send({"type": "http.response.start", "status": 200, "headers": [(b"x-protocol", b"native")]})
        await send({"type": "http.response.body", "body": b"dependency ", "more_body": True})
        assert lifecycle == ["open"]
        await send({"type": "http.response.body", "body": b"graph"})

    app.dependency_overrides[get_agent_streams_store] = stream_dependency
    app.dependency_overrides[get_blob_client] = lambda: blobs
    app.dependency_overrides[get_vercel_sandbox_client] = lambda: vercel
    app.add_middleware(RestateDependencies, dependency_overrides_provider=app)
    app.mount("/restate", protocol_app)
    with TestClient(app) as client:
        response = client.request(method, "/restate/discover", content=b"opaque protocol bytes")
    assert response.status_code == 200
    assert response.text == "dependency graph"
    assert response.headers["x-protocol"] == "native"
    assert lifecycle == ["open", "close"]


def test_restate_dependencies_do_not_apply_to_parent_routes(mocker: MockerFixture) -> None:
    app = FastAPI()
    dependency = mocker.Mock(side_effect=AssertionError("Restate dependencies reached an ordinary route"))
    app.dependency_overrides[get_agent_streams_store] = dependency
    app.add_middleware(RestateDependencies, dependency_overrides_provider=app)

    @app.get("/ordinary")
    async def ordinary() -> dict[str, str]:
        return {"status": "ok"}

    with TestClient(app) as client:
        assert client.get("/ordinary").json() == {"status": "ok"}
    dependency.assert_not_called()
