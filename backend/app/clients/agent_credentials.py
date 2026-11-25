"""Encrypted, account-scoped model connections and native OAuth persistence."""

import base64
import hashlib
import time
from typing import TYPE_CHECKING

import jwt
from cryptography.fernet import Fernet
from jwt.exceptions import InvalidTokenError
from pydantic import TypeAdapter
from pydantic_ai.providers.openai_chatgpt import OpenAIChatGPTCredentials
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.clients.database import SQLStore
from app.config import settings
from app.entities.agents import AgentCredential
from app.exceptions import InvalidInputError

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class AgentCredentialStore(SQLStore[AgentCredential]):
    """Keep secret material separate from prompts, traces, and execution journals."""

    def __init__(self, db: AsyncSession) -> None:
        """Bind one request or OAuth refresh transaction."""
        super().__init__(db, AgentCredential)

    @staticmethod
    def cipher(user_id: uuid.UUID, provider: str) -> Fernet:
        """Bind ciphertext to its owner/provider using the deployment's secret key."""
        key = hashlib.sha256(f"{settings.SECRET_KEY}:agent:{user_id}:{provider}".encode()).digest()
        return Fernet(base64.urlsafe_b64encode(key))

    async def list_for_user(self, user_id: uuid.UUID) -> list[AgentCredential]:
        """Return safe metadata to the account's owner."""
        return list(await self.db.scalars(select(AgentCredential).where(AgentCredential.user_id == user_id)))

    async def connection(self, user_id: uuid.UUID, provider: str, *, lock: bool = False) -> AgentCredential | None:
        """Find one account's connection, optionally locking refresh-token rotation."""
        statement = select(AgentCredential).where(
            AgentCredential.user_id == user_id, AgentCredential.provider == provider
        )
        if lock:
            statement = statement.with_for_update()
        return await self.db.scalar(statement)

    async def save_secret(self, user_id: uuid.UUID, provider: str, label: str, secret: str) -> AgentCredential:
        """Encrypt before writing; reject malformed ChatGPT credentials early."""
        if provider == "openai-chatgpt":
            try:
                credentials = TypeAdapter(OpenAIChatGPTCredentials).validate_json(secret)
            except ValueError as error:
                raise InvalidInputError("Invalid ChatGPT connection file") from error
            if not credentials.plan_usage_granted:
                raise InvalidInputError("ChatGPT plan usage was not granted")
        encrypted = self.cipher(user_id, provider).encrypt(secret.encode()).decode()
        statement = insert(AgentCredential).values(
            user_id=user_id, provider=provider, label=label, encrypted_secret=encrypted
        )
        await self.db.execute(
            statement.on_conflict_do_update(
                index_elements=[AgentCredential.user_id, AgentCredential.provider],
                set_={"label": label, "encrypted_secret": encrypted},
            )
        )
        await self.db.commit()
        connection = await self.connection(user_id, provider)
        if connection is None:
            raise RuntimeError("Connection was not saved")
        return connection

    async def remove(self, user_id: uuid.UUID, provider: str) -> None:
        """Revoke only this user's connection."""
        await self.db.execute(
            delete(AgentCredential).where(AgentCredential.user_id == user_id, AgentCredential.provider == provider)
        )
        await self.db.commit()

    def decrypt(self, connection: AgentCredential) -> str:
        """Decrypt only in the backend, after ownership checks."""
        return (
            self.cipher(connection.user_id, connection.provider).decrypt(connection.encrypted_secret.encode()).decode()
        )


class ChatGPTCredentialSource:
    """Persist rotated OAuth grants while the caller holds the connection row lock."""

    def __init__(self, store: AgentCredentialStore, connection: AgentCredential) -> None:
        """Use the model invocation's locked transaction."""
        self.store = store
        self.connection = connection

    async def load(self) -> OpenAIChatGPTCredentials:
        """Load the complete native PydanticAI credential bundle."""
        current = await self.store.connection(self.connection.user_id, self.connection.provider, lock=True)
        if current is None:
            raise InvalidInputError("ChatGPT connection was removed")
        self.connection = current
        credentials = TypeAdapter(OpenAIChatGPTCredentials).validate_json(self.store.decrypt(current))
        try:
            expiry = jwt.decode(credentials.access_token, options={"verify_signature": False, "verify_exp": False}).get(
                "exp"
            )
        except InvalidTokenError:
            expiry = None
        # This is only a refresh-scheduling hint; the native provider performs
        # authentication and grant validation. Expired tokens keep the row lock
        # through refresh and save; valid tokens release it immediately.
        if isinstance(expiry, (int, float)) and expiry > time.time() + 60:
            await self.store.db.commit()
        return credentials

    async def save(self, credentials: OpenAIChatGPTCredentials) -> None:
        """Keep refreshed tokens encrypted; commit before any other run can refresh."""
        value = TypeAdapter(OpenAIChatGPTCredentials).dump_json(credentials)
        self.connection.encrypted_secret = (
            self.store.cipher(self.connection.user_id, self.connection.provider).encrypt(value).decode()
        )
        await self.store.db.commit()
