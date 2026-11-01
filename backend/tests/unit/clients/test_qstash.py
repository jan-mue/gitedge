import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from qstash.errors import QStashError, SignatureError

from app.clients.qstash import QStashClient
from app.config import settings
from app.exceptions import InvalidDeliveryError
from app.schemas.action_dispatch import Delivery

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from pytest_mock import MockerFixture
    from respx import Router


@pytest.fixture
async def queue(mocker: MockerFixture) -> AsyncGenerator[QStashClient]:
    mocker.patch.object(settings, "QSTASH_URL", "https://qstash.test")
    mocker.patch.object(settings, "QSTASH_TOKEN", "unit-token")
    mocker.patch.object(settings, "QSTASH_CURRENT_SIGNING_KEY", "unit-current-key")
    mocker.patch.object(settings, "QSTASH_NEXT_SIGNING_KEY", "unit-next-key")
    client = QStashClient()
    yield client
    await client.close()


@pytest.mark.httpx2(using="httpcore")
async def test_publishing_delegates_deduplication_scheduling_and_retries_to_the_sdk(
    queue: QStashClient, httpx2_mock: Router
) -> None:
    body, due = Delivery(id=uuid.uuid4()), datetime.now(UTC) + timedelta(seconds=10)
    route = httpx2_mock.post(
        f"https://qstash.test/v2/publish/{queue.destination('dispatch')}",
        headers={
            "Authorization": "Bearer unit-token",
            "Upstash-Not-Before": str(int(due.timestamp())),
            "Upstash-Retries": "5",
            "Upstash-Retry-Delay": "1000",
            "Upstash-Timeout": f"{settings.ACTIONS_PROVISION_LEASE + 30}s",
        },
    ).respond(json={"messageId": "unit-delivery"})
    await queue.publish("dispatch", body, "stable-id", due)
    assert json.loads(route.calls.last.request.content) == body.model_dump(mode="json")
    assert re.fullmatch(r"[a-f0-9]{64}", route.calls.last.request.headers["Upstash-Deduplication-Id"])


@pytest.mark.httpx2(using="httpcore")
async def test_deduplication_keys_are_safe_stable_and_scoped_to_the_destination(
    queue: QStashClient, httpx2_mock: Router, mocker: MockerFixture
) -> None:
    route = httpx2_mock.post().respond(json={"messageId": "unit-delivery"})
    body, due = Delivery(id=uuid.uuid4()), datetime.now(UTC)
    key = f"{body.id}:123"
    for operation in ("dispatch", "dispatch", "inspect"):
        await queue.publish(operation, body, key, due)
    mocker.patch.object(settings, "ACTIONS_SERVER_URL", "https://another-backend.test")
    await queue.publish("dispatch", body, key, due)
    keys = [call.request.headers["Upstash-Deduplication-Id"] for call in route.calls]
    assert all(re.fullmatch(r"[a-f0-9]{64}", item) for item in keys)
    assert keys[0] == keys[1]
    assert len(set(keys)) == 3


@pytest.mark.httpx2(using="httpcore")
async def test_recovery_uses_a_valid_deduplication_key_and_the_next_time_slot(
    queue: QStashClient, httpx2_mock: Router, mocker: MockerFixture
) -> None:
    mocker.patch("app.clients.qstash.time.time", return_value=120)
    mocker.patch.object(settings, "ACTIONS_RECONCILE_INTERVAL", 60)
    route = httpx2_mock.post(f"https://qstash.test/v2/publish/{queue.destination('reconcile')}").respond(
        json={"messageId": "unit-recovery"}
    )
    await queue.recover_later()
    request = route.calls.last.request
    assert re.fullmatch(r"[a-f0-9]{64}", request.headers["Upstash-Deduplication-Id"])
    assert request.headers["Upstash-Not-Before"] == "180"
    assert json.loads(request.content) == {"version": 1, "slot": 180}


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


@pytest.mark.httpx2(using="httpcore")
async def test_sdk_publication_errors_reach_the_global_retry_handler(queue: QStashClient, httpx2_mock: Router) -> None:
    httpx2_mock.post(f"https://qstash.test/v2/publish/{queue.destination('dispatch')}").respond(503)
    with pytest.raises(QStashError):
        await queue.publish("dispatch", Delivery(id=uuid.uuid4()), "unavailable", datetime.now(UTC))
