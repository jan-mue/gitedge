"""Bounded QStash publishing and verification of the original delivery bytes."""

from __future__ import annotations

import base64
import hashlib
import math
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol
from urllib.parse import quote

import httpx2 as httpx
import jwt

from app.config import settings
from app.exceptions import ActionsUnavailableError, InvalidDeliveryError
from app.schemas.action_dispatch import RecoveryDelivery

if TYPE_CHECKING:
    from pydantic import BaseModel


class ActionsQueue(Protocol):
    """Publish durable HTTP commands and authenticate their delivery."""

    async def publish(self, operation: str, body: BaseModel, key: str, due_at: datetime) -> None:
        """Publish with bounded I/O, retries, and deterministic deduplication."""
        ...

    def verify(self, operation: str, body: bytes, signature: str) -> None:
        """Verify the exact destination and original delivery body."""
        ...

    async def recover_later(self) -> None:
        """Arm the next short-lived recovery callback."""
        ...


class QStashClient:
    """Use QStash HTTP delivery without a resident consumer."""

    def destination(self, operation: str) -> str:
        """Build the canonical URL whose signature must be verified."""
        return f"{settings.ACTIONS_SERVER_URL.rstrip('/')}/api/v1/actions/internal/{operation}"

    async def publish(self, operation: str, body: BaseModel, key: str, due_at: datetime) -> None:
        """Publish with bounded I/O, retries, and deterministic deduplication."""
        if not all((settings.QSTASH_TOKEN, settings.QSTASH_CURRENT_SIGNING_KEY, settings.QSTASH_NEXT_SIGNING_KEY)):
            raise ActionsUnavailableError("QStash publishing and signing credentials must be configured")
        delay = max(0, math.ceil((due_at - datetime.now(UTC)).total_seconds()))
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10, connect=3)) as client:
                response = await client.post(
                    f"{settings.QSTASH_URL.rstrip('/')}/v2/publish/{quote(self.destination(operation), safe=':/')}",
                    headers={
                        "Authorization": f"Bearer {settings.QSTASH_TOKEN}",
                        "Content-Type": "application/json",
                        "Upstash-Deduplication-Id": key,
                        "Upstash-Delay": f"{delay}s",
                        "Upstash-Retries": "5",
                        "Upstash-Retry-Delay": "1000",
                        "Upstash-Timeout": f"{settings.ACTIONS_PROVISION_LEASE + 30}s",
                    },
                    content=body.model_dump_json().encode(),
                )
                if not response.is_success:
                    raise ActionsUnavailableError(f"QStash returned HTTP {response.status_code}")
        except httpx.HTTPError as exc:
            raise ActionsUnavailableError("QStash publish failed") from exc

    async def recover_later(self) -> None:
        """Arm the next short-lived recovery callback."""
        interval = settings.ACTIONS_RECONCILE_INTERVAL
        slot = (int(time.time()) // interval + 1) * interval
        key = hashlib.sha256(f"{self.destination('reconcile')}:{slot}".encode()).hexdigest()
        await self.publish("reconcile", RecoveryDelivery(slot=slot), key, datetime.fromtimestamp(slot, UTC))

    def verify(self, operation: str, body: bytes, signature: str) -> None:
        """Verify the exact destination and original delivery body."""
        keys = (settings.QSTASH_CURRENT_SIGNING_KEY, settings.QSTASH_NEXT_SIGNING_KEY)
        expected = base64.urlsafe_b64encode(hashlib.sha256(body).digest()).decode().rstrip("=")
        for key in keys:
            if not key:
                continue
            try:
                claims = jwt.decode(
                    signature,
                    key,
                    algorithms=["HS256"],
                    issuer="Upstash",
                    options={"require": ["iss", "sub", "exp", "nbf", "body"]},
                )
            except jwt.InvalidTokenError:
                continue
            if (
                claims["sub"] == self.destination(operation)
                and isinstance(claims["body"], str)
                and claims["body"].rstrip("=") == expected
            ):
                return
        raise InvalidDeliveryError("Invalid QStash signature")
