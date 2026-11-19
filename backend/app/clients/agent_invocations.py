"""Durable submission transport, independent of workspace business rules."""

from typing import TYPE_CHECKING, Protocol

import restate

from app.agents.runtime import run
from app.config import settings

if TYPE_CHECKING:
    import uuid


class AgentInvocationClient(Protocol):
    """Submission boundary used by real ingress and in-memory tests."""

    async def submit(self, session_id: uuid.UUID, run_id: uuid.UUID) -> str:
        """Durably accept an idempotent turn and return its invocation ID."""
        ...


class RestateInvocationClient:
    """Submit only opaque run IDs; provider credentials never enter the journal."""

    async def submit(self, session_id: uuid.UUID, run_id: uuid.UUID) -> str:
        """Use a conversation-scoped object and globally unique run idempotency key."""
        headers = {"Authorization": f"Bearer {settings.RESTATE_AUTH_TOKEN}"} if settings.RESTATE_AUTH_TOKEN else {}
        async with restate.create_client(settings.RESTATE_INGRESS_URL, headers=headers) as client:
            handle = await client.object_send(run, key=str(session_id), arg=str(run_id), idempotency_key=str(run_id))
        return handle.invocation_id
