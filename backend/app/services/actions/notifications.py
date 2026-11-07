"""Durable failure delivery through the existing notification center."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from app.entities.activity import ActivityKind, ActivityTargetType
from app.schemas.actions import ActionJob
from app.schemas.workflow_events import EventActor, workflow_event_adapter

if TYPE_CHECKING:
    from app.clients.repositories import RepositoryStore
    from app.clients.users import UserStore
    from app.entities.actions import WorkflowRun
    from app.services.activity import ActivityService


class WorkflowFailureNotifications:
    """Turn final workflow failures into deduplicated activity notifications."""

    def __init__(self, activity: ActivityService, repositories: RepositoryStore, users: UserStore) -> None:
        """Use the existing permission-aware notification delivery service."""
        self.activity, self.repositories, self.users = activity, repositories, users

    async def actor(self, name: str) -> EventActor:
        """Pin the trusted event actor to an immutable user identity."""
        user = await self.users.find_by_name(name)
        return EventActor(login=name, id=user.id if user else None)

    async def notify(self, run: WorkflowRun) -> None:
        """Notify readers of a failed run without copying job logs or secrets."""
        if run.status != "failure":
            return
        event = workflow_event_adapter.validate_python({**run.event, "event_name": run.event_name})
        if event.sender is None or event.sender.id is None:
            return
        actor = await self.users.find(event.sender.id)
        repository = await self.repositories.find(run.repo_id)
        if actor is None or repository is None:
            return
        failed = [
            job.name
            for raw in run.jobs
            if (job := ActionJob.model_validate(raw)).status == "failure" and not job.continue_on_error
        ]
        title = f"{run.name} failed" + (f": {', '.join(failed[:3])}" if failed else "")
        await self.activity.record(
            event_id=uuid.uuid5(run.id, "workflow-failed"),
            actor=actor,
            repo=repository,
            kind=ActivityKind.WORKFLOW_FAILED,
            title=title[:512],
            target_type=ActivityTargetType.WORKFLOW_RUN,
            target_id=run.id,
        )
