"""Cooperative cancellation independent of model and workspace implementations."""

import asyncio
from typing import TYPE_CHECKING

import anyio

from app.clients.agent_streams import AgentRunCancelledError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


async def run_cancellable[T](action: Callable[[], Awaitable[T]], cancelled: Callable[[], Awaitable[bool]]) -> T:
    """Cancel an in-flight operation when its persisted stop request arrives."""
    if await cancelled():
        raise AgentRunCancelledError("Run stopped")

    async def wait_for_cancel() -> None:
        while not await cancelled():  # noqa: ASYNC110 - the stop request is persisted externally, not an in-process event
            await anyio.sleep(0.15)

    operation = asyncio.ensure_future(action())
    stop = asyncio.create_task(wait_for_cancel())
    try:
        completed, _pending = await asyncio.wait([operation, stop], return_when=asyncio.FIRST_COMPLETED)
        if stop in completed:
            await stop
            raise AgentRunCancelledError("Run stopped")
        return await operation
    finally:
        operation.cancel()
        stop.cancel()
        await asyncio.gather(operation, stop, return_exceptions=True)
