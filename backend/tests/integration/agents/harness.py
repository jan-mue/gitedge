"""Real Restate runtime with its ASGI endpoint on the clients' event loop."""

import asyncio
import socket
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import httpx2
import uvicorn
from restate import create_client
from restate.types import HarnessEnvironment

from tests.integration.agents.containers import RESTATE_IMAGE, AgentRestateContainer

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from starlette.types import ASGIApp


@asynccontextmanager
async def agent_harness(
    app: ASGIApp, *, disable_retries: bool = False, mount_path: str = ""
) -> AsyncGenerator[HarnessEnvironment]:
    """Configure the real container directly, without patching the SDK harness."""
    runtime = AgentRestateContainer(RESTATE_IMAGE, always_replay=True, disable_retries=disable_retries)
    runtime.with_env("RESTATE_DEFAULT_RETRY_POLICY__MAX_ATTEMPTS", "1" if disable_retries else "3")
    runtime.with_env("RESTATE_DEFAULT_RETRY_POLICY__ON_MAX_ATTEMPTS", "kill")
    with socket.socket() as listener:
        listener.bind(("0.0.0.0", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, lifespan="off", log_level="warning"))
        task = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            async with asyncio.timeout(30):
                while not server.started:
                    if task.done():
                        await task
                        raise RuntimeError("Agent endpoint stopped before startup")
                    await asyncio.sleep(0.01)
            await asyncio.to_thread(runtime.start)
            async with httpx2.AsyncClient(trust_env=False, timeout=60) as admin:
                response = await admin.post(
                    f"{runtime.admin_url()}/deployments",
                    json={"uri": f"http://host.docker.internal:{port}{mount_path}", "use_http_11": True},
                )
                if not response.is_success:
                    raise RuntimeError(f"Unable to register agent endpoint: {response.status_code} {response.text}")
            async with create_client(runtime.ingress_url()) as client:
                yield HarnessEnvironment(
                    ingress_url=runtime.ingress_url(), admin_api_url=runtime.admin_url(), client=client
                )
        finally:
            try:
                await asyncio.to_thread(runtime.stop)
            finally:
                server.should_exit = True
                await asyncio.wait_for(task, timeout=30)
