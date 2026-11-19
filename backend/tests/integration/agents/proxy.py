"""Drop one real Ollama response after its tokens have reached Redis."""

import asyncio
import json
import socket
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import httpx2
from aiohttp import web

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from app.clients.agent_streams import AgentStreamStore


@asynccontextmanager
async def interrupted_ollama(endpoint: str, streams: AgentStreamStore, run_id: str) -> AsyncGenerator[str]:
    """Forward actual model output, aborting only the first streamed connection."""
    interrupted = False
    async with httpx2.AsyncClient(timeout=300, trust_env=False) as upstream:

        async def forward(request: web.Request) -> web.StreamResponse:
            nonlocal interrupted
            body = await request.read()
            async with upstream.stream(
                request.method,
                f"{endpoint}{request.path_qs}",
                content=body,
                headers={"Content-Type": "application/json"},
            ) as response:
                response.raise_for_status()
                downstream = web.StreamResponse(
                    status=response.status_code, headers={"Content-Type": response.headers["content-type"]}
                )
                await downstream.prepare(request)
                content_seen = False
                async for line in response.aiter_lines():
                    await downstream.write((line + "\n").encode())
                    if line.startswith("data: ") and line != "data: [DONE]":
                        payload = json.loads(line[6:])
                        content_seen |= any(choice.get("delta", {}).get("content") for choice in payload["choices"])
                    if not interrupted and content_seen and not line:
                        interrupted = True
                        # Wait for persist-before-delivery, not a timing-dependent sleep.
                        async with asyncio.timeout(30):
                            async for event in streams.read(run_id):
                                if "TEXT_MESSAGE_CONTENT" in event:
                                    break
                        transport = request.transport
                        assert transport is not None
                        transport.abort()
                        return downstream
                await downstream.write_eof()
                return downstream

        app = web.Application()
        app.router.add_post("/v1/chat/completions", forward)
        runner = web.AppRunner(app)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            listener.setblocking(False)
            port = listener.getsockname()[1]
            await runner.setup()
            try:
                await web.SockSite(runner, listener).start()
                yield f"http://127.0.0.1:{port}/v1"
            finally:
                await runner.cleanup()
