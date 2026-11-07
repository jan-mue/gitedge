"""Authenticated agent workspace API contracts."""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
