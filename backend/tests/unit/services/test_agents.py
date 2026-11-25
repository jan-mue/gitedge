import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from app.clients.agent_credentials import AgentCredentialStore
from app.config import settings
from app.entities.agents import AgentCredential
from app.entities.users import User
from app.exceptions import InvalidInputError
from app.schemas.agents import CredentialCreate, RunCreate
from app.services.agents import AgentService

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.mark.parametrize("provider", ["opencode-zen", "opencode-go"])
async def test_native_opencode_connections_do_not_require_a_custom_endpoint(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    monkeypatch.setattr(settings, "AGENTS_OPENAI_ENDPOINTS", {})
    user = User(id=uuid.uuid4())
    credentials = mocker.create_autospec(AgentCredentialStore, instance=True)
    credentials.save_secret.return_value = AgentCredential(
        id=uuid.uuid4(),
        user_id=user.id,
        provider=provider,
        label="My OpenCode key",
        encrypted_secret="ciphertext",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service = AgentService(mocker.Mock(), credentials, mocker.Mock(), mocker.Mock(), mocker.Mock())
    body = CredentialCreate(label="My OpenCode key", secret="test-key")
    result = await service.save_connection(provider, body, user)
    assert result.provider == provider
    assert "test-key" not in result.model_dump_json()
    credentials.save_secret.assert_awaited_once_with(user.id, provider, body.label, "test-key")


@pytest.mark.parametrize("provider", ["opencode-zen", "opencode-go"])
@pytest.mark.parametrize("connected", [True, False])
async def test_opencode_submission_requires_owned_or_server_credentials(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch, provider: str, *, connected: bool
) -> None:
    monkeypatch.delenv(f"GITEDGE_{provider.upper().replace('-', '_')}_API_KEY", raising=False)
    user = User(id=uuid.uuid4())
    credentials = mocker.create_autospec(AgentCredentialStore, instance=True)
    credentials.connection.return_value = mocker.Mock() if connected else None
    store = mocker.Mock()
    store.request = mocker.AsyncMock(
        return_value=mocker.Mock(prompt="Hello", model=f"{provider}:hy4-flash-free", invocation_id="existing")
    )
    service = AgentService(mocker.Mock(), credentials, store, mocker.Mock(), mocker.Mock())
    session = mocker.Mock(id=uuid.uuid4(), archived=False)
    mocker.patch.object(service, "session", return_value=session)
    body = RunCreate(request_id=uuid.uuid4(), prompt="Hello", model=f"{provider}:hy4-flash-free")
    if connected:
        turn = await service.submit(session.id, body, user)
        assert turn.invocation_id == "existing"
    else:
        with pytest.raises(InvalidInputError, match=r"Connect OpenCode.*in AI credentials"):
            await service.submit(session.id, body, user)
        store.request.assert_not_awaited()


@pytest.mark.parametrize("model", ["opencode-go:minimax-m2.7", "opencode-zen:gemini-3.1-pro", "opencode-go:jev-1.14"])
async def test_removed_and_non_chat_opencode_models_are_rejected_before_enqueuing(
    mocker: MockerFixture, model: str
) -> None:
    store = mocker.Mock()
    service = AgentService(mocker.Mock(), mocker.Mock(), store, mocker.Mock(), mocker.Mock())
    session = mocker.Mock(id=uuid.uuid4(), archived=False)
    mocker.patch.object(service, "session", return_value=session)
    with pytest.raises(InvalidInputError, match="Unknown OpenCode chat model"):
        await service.submit(
            session.id, RunCreate(request_id=uuid.uuid4(), prompt="Hello", model=model), User(id=uuid.uuid4())
        )
    store.request.assert_not_called()
