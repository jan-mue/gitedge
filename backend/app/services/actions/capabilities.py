"""Short-lived capabilities are bound to the current job attempt and fence."""

from __future__ import annotations

from app.exceptions import PermissionDeniedError

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import jwt
from fastapi import HTTPException
from pydantic import ValidationError

from app.config import settings
from app.exceptions import WorkflowError
from app.schemas.action_dispatch import AttemptIdentity, Capability
from app.utils import security

if TYPE_CHECKING:
    import uuid

    from app.clients.actions import ActionsStore
    from app.entities.actions import WorkflowAttempt, WorkflowRun
    from app.schemas.actions import ActionJob


def issue_capability(run: WorkflowRun, job: ActionJob, attempt: WorkflowAttempt, scope: str) -> str:
    """Sign a purpose-limited capability for one attempt and fence."""
    return jwt.encode(
        {
            "sub": "actions",
            "repo": str(run.repo_id),
            "run": str(run.id),
            "job_id": job.id,
            "id": str(attempt.id),
            "generation": attempt.generation,
            "fence": str(attempt.fence),
            "scope": scope,
            "exp": datetime.now(UTC) + timedelta(seconds=job.timeout_seconds + settings.ACTIONS_PROVISION_LEASE + 60),
        },
        settings.SECRET_KEY,
        algorithm=security.ALGORITHM,
    )


async def authorize_capability(
    store: ActionsStore, token: str, scope: str, *, allow_terminal: bool = False
) -> Capability:
    """Authorize a signed capability against the current database generation."""
    try:
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
        capability = Capability.model_validate(claims)
    except (jwt.InvalidTokenError, ValueError) as error:
        raise PermissionDeniedError("Invalid sandbox token") from error
    if capability.scope != scope or not await store.current(capability, allow_terminal):
        raise PermissionDeniedError("Sandbox capability is stale or has the wrong scope")
    return capability


async def authorize_report(
    store: ActionsStore, attempt_id: uuid.UUID, authorization: str, *, terminal: bool = False
) -> Capability:
    """Bind a Bearer capability to the callback attempt."""
    capability = await authorize_capability(
        store, authorization.removeprefix("Bearer "), "actions:report", allow_terminal=terminal
    )
    if capability.id != attempt_id:
        raise PermissionDeniedError("Sandbox attempt does not match the callback")
    return capability


def report_payload[T: AttemptIdentity](model: type[T], body: bytes, capability: Capability) -> T:
    """Validate the report schema and exact attempt identity."""
    try:
        result = model.model_validate_json(body)
    except ValidationError as error:
        raise WorkflowError("Invalid sandbox report") from error
    if (result.id, result.job_id, result.generation, result.fence) != (
        capability.id,
        capability.job_id,
        capability.generation,
        capability.fence,
    ):
        raise PermissionDeniedError("Report belongs to another attempt")
    return result
