"""Queue deliveries and attempt-scoped capabilities."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

type DeliveryKind = Literal["dispatch", "inspect", "cleanup"]


class Delivery(BaseModel):
    """A versioned pointer to an authoritative outbox command."""

    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    id: uuid.UUID


class RecoveryDelivery(BaseModel):
    """The time bucket for a delayed recovery callback."""

    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    slot: int


class AttemptIdentity(BaseModel):
    """Identify the job generation allowed to publish execution results."""

    id: uuid.UUID
    job_id: str
    generation: int = Field(gt=0)
    fence: uuid.UUID


class Capability(AttemptIdentity):
    """Authorize one purpose for the current job attempt."""

    repo: uuid.UUID
    run: uuid.UUID
    scope: str
    exp: datetime
