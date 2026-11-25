"""Exercise @handler/@inject against real Restate and Redis, including schema round-tripping."""

import asyncio
from collections.abc import AsyncGenerator  # noqa: TC003 - injector inspects the provider signature
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from uuid import uuid4

import restate
from pydantic import BaseModel
from redis.asyncio import Redis
from uncalled_for import Depends

from app.agents.dependencies import inject
from tests.integration.agents.containers import RESTATE_IMAGE

if TYPE_CHECKING:
    from testcontainers.redis import RedisContainer


class InjectionInput(BaseModel):
    message: str


class InjectionOutput(BaseModel):
    message: str
    count: int


async def test_injected_handler_preserves_serde_and_cleans_up_on_server_loop(agent_redis: RedisContainer) -> None:
    url = f"redis://{agent_redis.get_container_host_ip()}:{agent_redis.get_exposed_port(6379)}/0"
    key = f"inject-test:{uuid4()}"
    lifecycle: list[tuple[str, int]] = []

    @asynccontextmanager
    async def connection() -> AsyncGenerator[Redis]:
        async with Redis.from_url(url, decode_responses=True) as client:
            lifecycle.append(("open", id(asyncio.get_running_loop())))
            try:
                yield client
            finally:
                lifecycle.append(("close", id(asyncio.get_running_loop())))

    service = restate.Service("DependencyInjectionTest")
    connection_dep = Depends(connection)

    @service.handler()
    @inject
    async def run(ctx: restate.Context, request: InjectionInput, client: Redis = connection_dep) -> InjectionOutput:
        async def increment() -> int:
            return int(await client.execute_command("INCR", key))

        count = await ctx.run_typed("increment once", increment)
        return InjectionOutput(message=request.message, count=count)

    async with restate.create_test_harness(
        restate.app([service], protocol="request_response"),
        restate_image=RESTATE_IMAGE,
        always_replay=True,
        disable_retries=True,
    ) as harness:
        result = await harness.client.service_call(run, arg=InjectionInput(message="typed input/output"))
        assert isinstance(result, InjectionOutput)
        assert result.message == "typed input/output"
        assert result.count == 1
    assert [loop for event, loop in lifecycle if event == "open"] == [
        loop for event, loop in lifecycle if event == "close"
    ]
    assert lifecycle
    async with Redis.from_url(url, decode_responses=True) as client:
        assert await client.get(key) == "1"
        await client.delete(key)
