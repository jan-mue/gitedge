"""QStash SDK adapter for durable Actions commands."""

from __future__ import annotations

import asyncio
import hashlib
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING, override

from qstash import AsyncQStash, Receiver
from qstash.errors import SignatureError

from app.config import settings
from app.exceptions import ActionsUnavailableError, InvalidDeliveryError
from app.schemas.action_dispatch import RecoveryDelivery

if TYPE_CHECKING:
    from pydantic import BaseModel


class ActionsQueue(ABC):
    """Durable delivery contract shared by QStash and unit-test fakes."""

    @abstractmethod
    async def publish(self, operation: str, body: BaseModel, key: str, due_at: datetime) -> None:
        """Publish an idempotent command for delivery at the requested time."""

    @abstractmethod
    def verify(self, operation: str, body: bytes, signature: str) -> None:
        """Authenticate the original delivery bytes and destination."""

    @abstractmethod
    async def recover_later(self) -> None:
        """Arm the next short recovery callback."""


class QStashClient(ActionsQueue):
    """Publish through the official SDK and verify the exact callback URL."""

    def __init__(self) -> None:
        """Reuse the SDK transport and rotating-key receiver for this application."""
        self.sdk = AsyncQStash(settings.QSTASH_TOKEN or "", base_url=settings.QSTASH_URL, retry=False)
        self.receiver = Receiver(settings.QSTASH_CURRENT_SIGNING_KEY or "", settings.QSTASH_NEXT_SIGNING_KEY or "")

    def destination(self, operation: str) -> str:
        """Build the canonical destination used for publishing and verification."""
        return f"{settings.ACTIONS_SERVER_URL.rstrip('/')}/api/v1/actions/internal/{operation}"

    @override
    async def publish(self, operation: str, body: BaseModel, key: str, due_at: datetime) -> None:
        """Bound SDK requests; the durable broker owns delivery retries."""
        if not all((settings.QSTASH_TOKEN, settings.QSTASH_CURRENT_SIGNING_KEY, settings.QSTASH_NEXT_SIGNING_KEY)):
            raise ActionsUnavailableError("QStash credentials must be configured")
        destination = self.destination(operation)
        deduplication_id = hashlib.sha256(f"{destination}\n{key}".encode()).hexdigest()
        async with asyncio.timeout(10):
            await self.sdk.message.publish_json(
                url=destination,
                body=body.model_dump(mode="json"),
                deduplication_id=deduplication_id,
                not_before=int(due_at.timestamp()),
                retries=5,
                retry_delay="1000",
                timeout=settings.ACTIONS_PROVISION_LEASE + 30,
            )

    @override
    async def recover_later(self) -> None:
        """Arm the next short-lived recovery callback without a cron schedule."""
        interval = settings.ACTIONS_RECONCILE_INTERVAL
        slot = (int(time.time()) // interval + 1) * interval
        await self.publish(
            "reconcile",
            RecoveryDelivery(slot=slot),
            f"{self.destination('reconcile')}:{slot}",
            datetime.fromtimestamp(slot, UTC),
        )

    @override
    def verify(self, operation: str, body: bytes, signature: str) -> None:
        """Pass original UTF-8 bytes and the canonical URL to the SDK receiver."""
        try:
            self.receiver.verify(body=body.decode(), signature=signature, url=self.destination(operation))
        except (SignatureError, UnicodeDecodeError, KeyError, TypeError) as error:
            raise InvalidDeliveryError("Invalid QStash signature") from error

    async def close(self) -> None:
        """Release the SDK transport when the application's lifespan ends."""
        await self.sdk.http._client.aclose()  # noqa: SLF001 — SDK has no public close method
