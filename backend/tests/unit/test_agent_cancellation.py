import asyncio

import anyio
import pytest

from app.agents.cancellation import run_cancellable
from app.clients.agent_streams import AgentRunCancelledError


async def test_operation_returns_its_result() -> None:
    async def action() -> str:
        return "done"

    async def cancelled() -> bool:
        return False

    assert await run_cancellable(action, cancelled) == "done"


async def test_existing_stop_request_does_not_start_the_operation() -> None:
    async def action() -> None:
        pytest.fail("Cancelled operation was started")

    async def cancelled() -> bool:
        return True

    with pytest.raises(AgentRunCancelledError):
        await run_cancellable(action, cancelled)


async def test_stop_request_cancels_a_silent_operation_and_waits_for_cleanup() -> None:
    started = asyncio.Event()
    cleaned = asyncio.Event()
    stopped = False

    async def action() -> None:
        try:
            started.set()
            await anyio.sleep_forever()
        finally:
            cleaned.set()

    async def cancelled() -> bool:
        return stopped

    task = asyncio.create_task(run_cancellable(action, cancelled))
    await started.wait()
    stopped = True
    with pytest.raises(AgentRunCancelledError):
        await task
    assert cleaned.is_set()


async def test_operation_errors_are_not_replaced() -> None:
    error = ValueError("operation failed")

    async def action() -> None:
        raise error

    async def cancelled() -> bool:
        return False

    with pytest.raises(ValueError, match="operation failed") as caught:
        await run_cancellable(action, cancelled)
    assert caught.value is error
