"""Short-lived capabilities are bound to the current job attempt and fence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import jwt

from app.config import settings
from app.exceptions import PermissionDeniedError
from app.schemas.action_dispatch import Capability
from app.utils import security

if TYPE_CHECKING:
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
