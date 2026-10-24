"""Publish committed commands; acknowledgment is a separate database transition."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.exceptions import ActionsUnavailableError
from app.schemas.action_dispatch import Delivery

if TYPE_CHECKING:
    from app.clients.actions import ActionsStore
    from app.clients.qstash import ActionsQueue


class OutboxPublisher:
    """Publish committed commands and record durable acceptance."""

    def __init__(self, store: ActionsStore, queue: ActionsQueue) -> None:
        """Publish only commands already committed by the store."""
        self.store, self.queue = store, queue

    async def flush(self, *, arm_recovery: bool = True) -> None:
        """Publish a bounded page of pending commands after commit."""
        if arm_recovery:
            await self.queue.recover_later()
        try:
            async with asyncio.timeout(15):
                for message in await self.store.pending(limit=25):
                    now = datetime.now(UTC)
                    publication = int(now.timestamp()) // 60
                    await self.queue.publish(
                        message.kind, Delivery(id=message.id), f"{message.id}:{publication}", message.due_at
                    )
                    await self.store.published(message.id, now)
        except TimeoutError as error:
            raise ActionsUnavailableError("Outbox publishing must be retried") from error
