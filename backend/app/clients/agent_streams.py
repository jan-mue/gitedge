"""Persist-before-delivery streams usable with Redis TCP and Upstash REST."""

import asyncio
import json
import re
from typing import TYPE_CHECKING, Protocol, cast

from restate import TerminalError
from upstash_redis.asyncio import Redis

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    import redis.asyncio as redis

# A logical event can be retried after XADD but before Restate journals success.
_APPEND = """
local prior = redis.call('HGET', KEYS[2], ARGV[1])
if prior then return prior end
local id = redis.call('XADD', KEYS[1], '*', 'event', ARGV[2])
redis.call('HSET', KEYS[2], ARGV[1], id)
redis.call('EXPIRE', KEYS[1], 604800)
redis.call('EXPIRE', KEYS[2], 604800)
return id
"""


class AgentRunCancelledError(TerminalError):
    """An authorized user requested cooperative cancellation."""


class AgentEventStore(Protocol):
    """Persistence interface shared by real Redis stores and in-memory tests."""

    async def append(self, run_id: str, event_id: str, event: str) -> str:
        """Save an event idempotently."""
        ...

    async def history(self, run_id: str) -> list[str]:
        """Return ordered native events for transformer reconstruction."""
        ...

    async def attempt(self, run_id: str, step: int) -> int:
        """Allocate a new streamed model attempt."""
        ...

    async def cancelled(self, run_id: str) -> bool:
        """Check a durable cancellation request."""
        ...


class AgentStreamStore:
    """Keep encoded AG-UI events, preserving transformer state across reconnects."""

    def __init__(self, client: redis.Redis | Redis) -> None:
        """Accept either configured Redis transport."""
        self.client = client

    async def append(self, run_id: str, event_id: str, event: str) -> str:
        """Append once per logical event before any browser can observe it."""
        keys = [f"agents:{{{run_id}}}:events", f"agents:{{{run_id}}}:dedup"]
        if isinstance(self.client, Redis):
            result = await self.client.eval(_APPEND, keys=keys, args=[event_id, event])
        else:
            result = await self.client.eval(_APPEND, 2, *keys, event_id, event)
        return result.decode() if isinstance(result, bytes) else str(result)

    async def read(self, run_id: str, cursor: str = "0-0") -> AsyncIterator[str]:
        """Replay from an exclusive cursor, polling without blocking REST calls."""
        if re.fullmatch(r"\d+-\d+", cursor) is None:
            raise ValueError("Invalid stream cursor")
        key = f"agents:{{{run_id}}}:events"
        while True:
            if isinstance(self.client, Redis):
                result = await self.client.xread({key: cursor}, count=100)
            else:
                result = await self.client.xread({key: cursor}, count=100)
            batches = cast(
                list[tuple[str, list[tuple[str, dict[str, str]]]]],
                list(result.items()) if isinstance(result, dict) else (result or []),
            )
            found = False
            for _stream, entries in batches:
                for position, fields in entries:
                    found = True
                    cursor = position.decode() if isinstance(position, bytes) else str(position)
                    payload = fields.get("event") if "event" in fields else fields.get(b"event")
                    if payload is None:
                        raise ValueError("Corrupt agent stream entry")
                    if isinstance(payload, bytes):
                        payload = payload.decode()
                    yield f"id: {cursor}\ndata: {payload}\n\n"
                    if json.loads(payload)["type"] in {"RUN_FINISHED", "RUN_ERROR"}:
                        return
            if not found:
                yield ": keepalive\n\n"
                await asyncio.sleep(0.15)

    async def history(self, run_id: str) -> list[str]:
        """Read native events to rebuild the AG-UI transformer on execution replay."""
        key = f"agents:{{{run_id}}}:events"
        result = await self.client.xread({key: "0-0"})
        batches = cast(
            list[tuple[str, list[tuple[str, dict[str, str]]]]],
            list(result.items()) if isinstance(result, dict) else (result or []),
        )
        payloads = []
        for _stream, entries in batches:
            for _position, fields in entries:
                payload = fields.get("event") if "event" in fields else fields.get(b"event")
                if isinstance(payload, bytes):
                    payload = payload.decode()
                if payload is not None:
                    payloads.append(str(payload))
        return payloads

    async def attempt(self, run_id: str, step: int) -> int:
        """Allocate an attempt only when an actual model request executes, never on journal replay."""
        key = f"agents:{{{run_id}}}:model:{step}:attempt"
        if isinstance(self.client, Redis):
            result = await self.client.incr(key)
            await self.client.expire(key, 604800)
        else:
            result = await self.client.execute_command("INCR", key)
            await self.client.execute_command("EXPIRE", key, 604800)
        return int(result)

    async def cancel(self, run_id: str) -> None:
        """Persist cancellation independently of the browser connection."""
        await self.client.set(f"agents:{{{run_id}}}:cancel", "1", ex=604800)

    async def cancelled(self, run_id: str) -> bool:
        """Check cancellation while a model or detached command is running."""
        return bool(await self.client.get(f"agents:{{{run_id}}}:cancel"))
