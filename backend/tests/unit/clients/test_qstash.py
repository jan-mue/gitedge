import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from qstash.errors import SignatureError

from app.clients.qstash import QStashClient
from app.config import settings
from app.exceptions import InvalidDeliveryError
from app.schemas.action_dispatch import Delivery

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from pytest_mock import MockerFixture


@pytest.fixture
async def queue(mocker: MockerFixture) -> AsyncGenerator[QStashClient]:
    mocker.patch.object(settings, "QSTASH_TOKEN", "unit-token")
    mocker.patch.object(settings, "QSTASH_CURRENT_SIGNING_KEY", "unit-current-key")
    mocker.patch.object(settings, "QSTASH_NEXT_SIGNING_KEY", "unit-next-key")
    client = QStashClient()
    yield client
    await client.close()


async def test_publishing_delegates_deduplication_scheduling_and_retries_to_the_sdk(
    queue: QStashClient, mocker: MockerFixture
) -> None:
    publish = mocker.patch.object(queue.sdk.message, "publish_json", new_callable=mocker.AsyncMock)
    body, due = Delivery(id=uuid.uuid4()), datetime.now(UTC) + timedelta(seconds=10)
    await queue.publish("dispatch", body, "stable-id", due)
    publish.assert_awaited_once_with(
        url=queue.destination("dispatch"),
        body=body.model_dump(mode="json"),
        deduplication_id="stable-id",
        not_before=int(due.timestamp()),
        retries=5,
        retry_delay="1000",
        timeout=settings.ACTIONS_PROVISION_LEASE + 30,
    )


async def test_verification_passes_original_body_and_exact_url_to_the_sdk(
    queue: QStashClient, mocker: MockerFixture
) -> None:
    verify = mocker.patch.object(queue.receiver, "verify")
    body = '{ "unicode": "é", "version": 1 }'
    queue.verify("dispatch", body.encode(), "signature")
    verify.assert_called_once_with(body=body, signature="signature", url=queue.destination("dispatch"))
    verify.side_effect = SignatureError("invalid signature")
    with pytest.raises(InvalidDeliveryError):
        queue.verify("dispatch", body.encode(), "forged")
    with pytest.raises(InvalidDeliveryError):
        queue.verify("dispatch", b"\xff", "forged")
