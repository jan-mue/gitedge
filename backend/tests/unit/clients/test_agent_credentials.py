import uuid

import pytest
from cryptography.fernet import InvalidToken

from app.clients.agent_credentials import AgentCredentialStore


def test_credentials_are_bound_to_owner_and_provider() -> None:
    user_id = uuid.uuid4()
    cipher = AgentCredentialStore.cipher(user_id, "openai")
    encrypted = cipher.encrypt(b"test-key")
    assert b"test-key" not in encrypted
    assert cipher.decrypt(encrypted) == b"test-key"
    with pytest.raises(InvalidToken):
        AgentCredentialStore.cipher(uuid.uuid4(), "openai").decrypt(encrypted)
    with pytest.raises(InvalidToken):
        AgentCredentialStore.cipher(user_id, "opencode-go").decrypt(encrypted)
