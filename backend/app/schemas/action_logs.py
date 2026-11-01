"""Versioned agent uploads and paginated log history."""

import uuid
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.action_dispatch import AttemptIdentity
from app.schemas.actions import ActionStatus

LOG_CHUNK_BYTES = 256 * 1024
LOG_PAGE_BYTES = 256 * 1024
LOG_STREAM_SECONDS = 20


class LogRecord(BaseModel):
    """One ordered fragment, optionally ending an output line."""

    model_config = ConfigDict(extra="forbid")
    seq: int = Field(ge=1)
    msg: str = Field(max_length=4096)
    step_id: str | None = Field(default=None, max_length=255)
    status: ActionStatus | None = None
    end: bool = True


class LogChunk(AttemptIdentity):
    """An immutable, contiguous upload scoped to one attempt."""

    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    from_seq: int = Field(ge=1)
    to_seq: int = Field(ge=1)
    records: list[LogRecord] = Field(min_length=1, max_length=1024)

    @model_validator(mode="after")
    def contiguous(self) -> Self:
        """Reject gaps, duplicate sequences and inconsistent ranges."""
        if len(self.records) != self.to_seq - self.from_seq + 1 or any(
            record.seq != self.from_seq + offset for offset, record in enumerate(self.records)
        ):
            raise ValueError("Log records must be contiguous and match their chunk range")
        return self


class StepResult(BaseModel):
    """Terminal step outcome and effective conclusion."""

    outcome: Literal["success", "failure", "cancelled", "skipped"]
    conclusion: Literal["success", "failure", "cancelled", "skipped"]
    outputs: dict[str, str] = Field(default_factory=dict)


class JobResult(BaseModel):
    """Structured execution metadata without log payloads."""

    status: Literal["success", "failure", "cancelled", "skipped"]
    steps: dict[str, StepResult] = Field(default_factory=dict)
    outputs: dict[str, str] = Field(default_factory=dict)
    error: str | None = None


class JobCompletion(AttemptIdentity):
    """Fenced terminal result with the final acknowledged cursor."""

    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    exit_code: int
    last_seq: int = Field(ge=0)
    result: JobResult


class LogPage(BaseModel):
    """A bounded replay page and its resume cursor."""

    attempt_id: uuid.UUID
    records: list[LogRecord]
    next_seq: int
    complete: bool
