"""Typed Git event adaptation, independent of workflow parsing and scheduling."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.config import settings
from app.entities.issues import IssueState
from app.entities.principals import PrincipalType
from app.exceptions import WorkflowError
from app.schemas.workflow_events import (
    DispatchEvent,
    EventActor,
    EventRepository,
    PullRequestContext,
    PullRequestEvent,
    PullRequestRef,
    PushEvent,
    WorkflowEvent,
)
from app.schemas.workflows import CompileEvent
from app.services.actions.workflows import workflow_paths

if TYPE_CHECKING:
    from app.clients.pull_requests import PullRequestStore
    from app.clients.repositories import RepositoryStore
    from app.entities.repositories import Repository as RepositoryEntity
    from app.entities.users import User
    from app.schemas.actions import ActionRun
    from app.services.repositories import RepositoryService


class WorkflowTrigger(Protocol):
    """Accept typed events without parsing the workflow language."""

    async def __call__(
        self,
        owner: str,
        name: str,
        ref: str,
        event: WorkflowEvent,
        *,
        actor: str,
        workflow: str | None = None,
        event_key: str | None = None,
    ) -> list[ActionRun]:
        """Trigger workflows for an authorized repository event."""
        ...


def snapshot_event(
    event: WorkflowEvent, repository: RepositoryEntity, owner: str, name: str, sha: str, canonical: str, actor: str
) -> WorkflowEvent:
    """Pin the event actor and repository to the resolved revision."""
    return event.model_copy(
        update={
            "ref": event.ref or canonical,
            "after": sha,
            "repository": EventRepository(
                full_name=f"{owner}/{name}",
                name=name,
                default_branch=repository.default_branch,
                private=repository.is_private,
                html_url=f"{settings.ACTIONS_SERVER_URL}/{owner}/{name}",
                clone_url=f"{settings.ACTIONS_SERVER_URL}/{owner}/{name}.git",
                owner=EventActor(
                    login=owner,
                    name=repository.owner.display_name or owner,
                    type="Organization" if repository.owner.principal_type == PrincipalType.ORGANIZATION else "User",
                ),
            ),
            "sender": EventActor(login=actor),
        }
    )


def compile_event(event: WorkflowEvent, owner: str, name: str) -> CompileEvent:
    """Adapt supported typed events to the compiler request context."""
    if not isinstance(event, PushEvent | PullRequestEvent | DispatchEvent):
        raise WorkflowError(f"Unsupported workflow event: {event.event_name}")
    context = CompileEvent(
        name=event.event_name,
        ref=event.ref,
        changed_paths=event.changed_paths,
        repository=f"{owner}/{name}",
    )
    if isinstance(event, PullRequestEvent):
        context.action = event.action
        context.base_ref = event.pull_request.base.ref
    if isinstance(event, DispatchEvent):
        context.inputs = dict(event.inputs)
    return context


class WorkflowEvents:
    """Adapt repository changes into typed workflow events."""

    def __init__(
        self,
        repositories: RepositoryService,
        repository_store: RepositoryStore,
        pull_requests: PullRequestStore | None,
        trigger: WorkflowTrigger,
    ) -> None:
        """Resolve Git event context before invoking the workflow compiler."""
        self.repositories, self.repository_store = repositories, repository_store
        self.pull_requests, self.trigger = pull_requests, trigger

    async def on_push(self, owner: str, name: str, before: dict[str, str], after: dict[str, str], user: User) -> None:
        """Accept CI events only from an authenticated repository owner or administrator."""
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        pulls = await self.pull_requests.list_by_repo(repository.id, IssueState.OPEN) if self.pull_requests else []
        for ref, sha in after.items():
            old = before.get(ref)
            if old == sha:
                continue
            if old:
                comparison = await self.repositories.compare(owner, name, old, sha, include_diff=False)
                paths = [file.path for file in comparison.files]
            else:
                paths = (await self.repositories.get_file_index(owner, name, sha)).paths
            await self.trigger(
                owner,
                name,
                sha,
                PushEvent(ref=ref, before=old or "0" * 40, changed_paths=paths),
                actor=user.name,
                event_key=f"push:{ref}:{old}:{sha}",
            )
            for pull in pulls:
                if ref == f"refs/heads/{pull.head_branch}":
                    await self.on_pull_request(
                        owner, name, pull.number, pull.head_branch, pull.base_branch, user, action="synchronize"
                    )

    async def on_pull_request(
        self,
        owner: str,
        name: str,
        number: int,
        head_branch: str,
        base_branch: str,
        user: User,
        *,
        action: str = "opened",
    ) -> None:
        """Trigger opened PR workflows using the submitted head and base context."""
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        if user.id != repository.owner_id and not user.is_superuser:
            return
        index = await self.repositories.get_file_index(owner, name, head_branch)
        if not workflow_paths(index.paths):
            return
        sha, _ = await self.repositories.action_revision(owner, name, head_branch)
        base_sha, _ = await self.repositories.action_revision(owner, name, base_branch)
        comparison = await self.repositories.compare(owner, name, base_sha, sha, include_diff=False)
        event = PullRequestEvent(
            action=action,
            number=number,
            ref=f"refs/heads/{head_branch}",
            changed_paths=[file.path for file in comparison.files],
            pull_request=PullRequestContext(
                number=number,
                head=PullRequestRef(ref=head_branch, sha=sha),
                base=PullRequestRef(ref=base_branch, sha=base_sha),
            ),
        )
        await self.trigger(owner, name, sha, event, actor=user.name, event_key=f"pr:{number}:{action}:{sha}")
