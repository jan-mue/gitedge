"""Authenticated agent workspace API contracts."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class EnvironmentCreate(BaseModel):
    """Create a repository collection and its setup instructions."""

    name: str = Field(min_length=1, max_length=200)
    repositories: list[str] = Field(min_length=1, max_length=20)
    setup_script: str = Field(default="", max_length=100_000)
    instructions: str = Field(default="", max_length=100_000)


class EnvironmentPublic(BaseModel):
    """Environment metadata without provider credentials."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    snapshot_id: str | None
    setup_script: str
    instructions: str
    repositories: list[str] = Field(default_factory=list)


class SessionCreate(BaseModel):
    """Start a setup chat or fork the environment's prepared image."""

    environment_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    kind: Literal["setup", "coding"] = "coding"


class SessionPublic(BaseModel):
    """Conversation listing entry."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    environment_id: uuid.UUID
    title: str
    kind: str
    pinned: bool = False
    archived: bool = False
    active_run: uuid.UUID | None = None


class RunCreate(BaseModel):
    """Idempotent turn submission with a provider-qualified model."""

    request_id: uuid.UUID
    prompt: str = Field(min_length=1, max_length=100_000)
    model: str = Field(min_length=1, max_length=250)


class RunPublic(BaseModel):
    """Turn state and durable invocation reference."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    session_id: uuid.UUID
    status: str
    invocation_id: str | None
    error: str | None
    prompt: str
    model: str
    created_at: datetime
    finished_at: datetime | None


class EnvironmentUpdate(BaseModel):
    """Edit setup configuration; the next setup run publishes a new base image."""

    name: str = Field(min_length=1, max_length=200)
    setup_script: str = Field(default="", max_length=100_000)
    instructions: str = Field(default="", max_length=100_000)


class SessionUpdate(BaseModel):
    """Persistent sidebar preferences."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    pinned: bool | None = None
    archived: bool | None = None


class CredentialCreate(BaseModel):
    """A provider key or JSON OAuth credential bundle, accepted only over authenticated TLS."""

    label: str = Field(min_length=1, max_length=200)
    secret: SecretStr = Field(min_length=1, max_length=100_000)


class CredentialPublic(BaseModel):
    """Safe connection metadata; credentials cannot be read back by the browser."""

    model_config = ConfigDict(from_attributes=True)
    provider: str
    label: str


class ProviderPublic(BaseModel):
    """Supported account connections without endpoint secrets."""

    provider: str
    label: str
    auth: Literal["key", "chatgpt"] = "key"
