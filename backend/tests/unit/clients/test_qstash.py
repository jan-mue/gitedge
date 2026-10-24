import base64
import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import httpx2 as httpx
import jwt
import pytest

from app.clients.qstash import QStashClient
from app.config import settings
from app.exceptions import ActionsUnavailableError, InvalidDeliveryError
from app.schemas.action_dispatch import Delivery

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture
def queue(mocker: MockerFixture) -> QStashClient:
    mocker.patch.object(settings, "QSTASH_CURRENT_SIGNING_KEY", "current-signing-key-for-unit-tests")
    mocker.patch.object(settings, "QSTASH_NEXT_SIGNING_KEY", "next-signing-key-for-unit-tests-32")
    mocker.patch.object(settings, "QSTASH_TOKEN", "unit-publish-token")
    return QStashClient()


def signed(
    queue: QStashClient, raw: bytes, *, key: str | None = None, overrides: dict[str, str | int] | None = None
) -> str:
    now = datetime.now(UTC)
    claims = {
        "iss": "Upstash",
        "sub": queue.destination("dispatch"),
        "nbf": now - timedelta(seconds=1),
        "exp": now + timedelta(seconds=60),
        "body": base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip("="),
    }
    signing_key = key or settings.QSTASH_CURRENT_SIGNING_KEY
    assert signing_key is not None
    return jwt.encode({**claims, **(overrides or {})}, signing_key, algorithm="HS256")


@pytest.mark.parametrize("rotated", [False, True])
def test_qstash_verifies_the_original_body_url_and_rotating_keys(queue: QStashClient, rotated: bool) -> None:
    body = b'{ "id" : "original formatting" }'
    signature = signed(queue, body, key=settings.QSTASH_NEXT_SIGNING_KEY if rotated else None)
    queue.verify("dispatch", body, signature)
    for operation, payload in [("inspect", body), ("dispatch", body.replace(b" ", b""))]:
        with pytest.raises(InvalidDeliveryError):
            queue.verify(operation, payload, signature)


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "Other"},
        {"exp": 1},
        {"nbf": 4102444800},
        {"body": "wrong"},
        {"sub": "http://another-host/actions/internal/dispatch"},
    ],
)
def test_qstash_rejects_invalid_claims(queue: QStashClient, claims: dict[str, str | int]) -> None:
    body = b"{}"
    with pytest.raises(InvalidDeliveryError):
        queue.verify("dispatch", body, signed(queue, body, overrides=claims))


async def test_publisher_sends_a_deterministic_id_signed_destination_and_delay(
    queue: QStashClient, mocker: MockerFixture
) -> None:
    delivery = Delivery(id=uuid.uuid4())

    def response(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer unit-publish-token"
        assert request.headers["upstash-deduplication-id"] == "stable-id"
        assert request.headers["upstash-retries"] == "5"
        assert request.headers["upstash-delay"].endswith("s")
        assert request.content == delivery.model_dump_json().encode()
        assert str(request.url).endswith(queue.destination("dispatch"))
        return httpx.Response(200, json={"messageId": "durable-message"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(response))
    mocker.patch("app.clients.qstash.httpx.AsyncClient", return_value=client)
    await queue.publish("dispatch", delivery, "stable-id", datetime.now(UTC) + timedelta(seconds=10))


async def test_publish_errors_remain_retryable(queue: QStashClient, mocker: MockerFixture) -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: httpx.Response(503)))
    mocker.patch("app.clients.qstash.httpx.AsyncClient", return_value=client)
    with pytest.raises(ActionsUnavailableError):
        await queue.publish("dispatch", Delivery(id=uuid.uuid4()), "stable", datetime.now(UTC))
