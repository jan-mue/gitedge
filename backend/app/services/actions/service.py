"""Event-driven workflow scheduling with one ephemeral sandbox per expanded job."""

from __future__ import annotations

import gzip
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import jwt
from fastapi import HTTPException

from app.config import settings
from app.entities.actions import WorkflowRun
from app.entities.issues import IssueState
from app.entities.principals import PrincipalType
from app.exceptions import WorkflowError
from app.schemas.actions import ActionJob, ActionRun, ActionStatus, PullRequestChecks, WorkflowInfo
from app.schemas.workflow_events import (
    DispatchEvent,
    EventActor,
    EventRepository,
    PullRequestContext,
    PullRequestEvent,
    PullRequestRef,
    PushEvent,
    WorkflowEvent,
    workflow_event_adapter,
)
from app.schemas.workflows import CompileEvent, CompileRequest
from app.services.actions.scheduler import TERMINAL, RunScheduler
from app.services.actions.workflows import instantiate_jobs, workflow_paths
from app.utils import security

if TYPE_CHECKING:
    from app.clients.actions import ActionsStore
    from app.clients.blob_storage import BlobStorageClient
    from app.clients.pull_requests import PullRequestStore
    from app.clients.repositories import RepositoryStore
    from app.clients.sandboxes import AbstractSandboxClient
    from app.clients.workflow_compiler import WorkflowCompiler
    from app.entities.repositories import Repository as RepositoryEntity
    from app.entities.users import User
    from app.schemas.actions_cache import CacheEntry, CacheIdentity
    from app.services.actions.cache import ActionsCacheService
    from app.services.repositories import RepositoryService

logger = logging.getLogger(__name__)


class ActionsService:
    """Advance persisted runs from workflow events and sandbox completion callbacks."""

    def __init__(
        self,
        store: ActionsStore,
        repositories: RepositoryService,
        repository_store: RepositoryStore,
        blobs: BlobStorageClient,
        sandbox: AbstractSandboxClient,
        *,
        compiler: WorkflowCompiler,
        provider: str,
        max_timeout: int,
        max_parallel: int,
        secrets: dict[str, dict[str, str]] | None = None,
        pull_requests: PullRequestStore | None = None,
        cache: ActionsCacheService | None = None,
    ) -> None:
        """Inject data access and sandbox clients; keep provider policy out of workflows."""
        self.compiler = compiler
        self.store = store
        self.repositories = repositories
        self.repository_store = repository_store
        self.blobs = blobs
        self.provider = provider
        self.max_timeout = max_timeout
        self.pull_requests = pull_requests
        self.cache = cache
        self.scheduler = RunScheduler(store, blobs, sandbox, max_parallel, secrets or {})

    async def _repository(
        self, owner: str, name: str, user: User | None = None, *, write: bool = False
    ) -> RepositoryEntity:
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        allowed = user is not None and (user.id == repository.owner_id or user.is_superuser)
        if repository.is_private and not allowed:
            raise HTTPException(status_code=404, detail="Repository not found")
        if write and not allowed:
            raise HTTPException(status_code=403, detail="Only the repository owner can dispatch or cancel workflows")
        return repository

    async def workflows(self, owner: str, name: str, ref: str, user: User | None) -> list[WorkflowInfo]:
        """Discover workflow files at a requested revision."""
        await self._repository(owner, name, user)
        index = await self.repositories.get_file_index(owner, name, ref)
        if not index.paths:
            return []
        sha, _ = await self.repositories.action_revision(owner, name, ref)
        result = []
        for path in workflow_paths(index.paths):
            raw = await self.repositories.get_raw(owner, name, sha, path, follow_symlinks=True)
            compiled = await self.compiler.compile(
                CompileRequest(filename=path, source=raw.decode(), event=CompileEvent(name="push", ref=ref))
            )
            result.append(WorkflowInfo(path=path, name=compiled.workflow_name, dispatch=compiled.dispatch))
        return result

    async def dispatch(
        self, owner: str, name: str, workflow: str, ref: str, inputs: dict[str, str], user: User
    ) -> ActionRun:
        """Authorize a manual dispatch before provisioning any job resources."""
        await self._repository(owner, name, user, write=True)
        runs = await self.trigger(owner, name, ref, DispatchEvent(inputs=inputs), actor=user.name, workflow=workflow)
        if not runs:
            raise HTTPException(status_code=422, detail="Workflow does not enable workflow_dispatch")
        return runs[0]

    async def trigger(
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
        """Snapshot triggered workflows at the exact event commit; deduplicate deliveries."""
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        initial_index = await self.repositories.get_file_index(owner, name, ref)
        if not workflow and not workflow_paths(initial_index.paths):
            return []
        sha, canonical = await self.repositories.action_revision(owner, name, ref)
        index = await self.repositories.get_file_index(owner, name, sha)
        event = event.model_copy(
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
                        type="Organization"
                        if repository.owner.principal_type == PrincipalType.ORGANIZATION
                        else "User",
                    ),
                ),
                "sender": EventActor(login=actor),
            }
        )
        run_ids = []
        for path in workflow_paths(index.paths, workflow):
            raw = (await self.repositories.get_raw(owner, name, sha, path, follow_symlinks=True)).decode()
            compiled = None
            error = None
            jobs: list[ActionJob] = []
            try:
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
                compiled = await self.compiler.compile(CompileRequest(filename=path, source=raw, event=context))
                if not compiled.matched:
                    continue
                jobs = instantiate_jobs(compiled, self.max_timeout)
            except WorkflowError as exc:
                logger.warning("Invalid workflow %s in %s/%s: %s", path, owner, name, exc)
                error = str(exc)
            run = WorkflowRun(
                id=uuid.uuid4(),
                repo_id=repository.id,
                workflow=path,
                definition=raw,
                name=compiled.workflow_name if compiled else path,
                compiled=compiled.model_dump(mode="json", by_alias=True, exclude_none=True) if compiled else None,
                sha=sha,
                ref=event.ref,
                actor=actor,
                event_name=event.event_name,
                event_key=event_key or uuid.uuid4().hex,
                event=event.model_dump(mode="json"),
                provider=self.provider,
                status="failure" if error else "queued",
                jobs=[job.model_dump(mode="json") for job in jobs],
                error=error,
                completed_at=datetime.now(UTC) if error else None,
            )
            run = await self.store.add_run(run)
            run_ids.append(run.id)
        if workflow and not run_ids:
            raise HTTPException(status_code=422, detail="Workflow not found or event is not enabled")
        for run_id in run_ids:
            await self.scheduler.advance(repository.id, run_id)
        return [self.public(run) for run in await self.store.list_runs(repository.id) if run.id in run_ids]

    @staticmethod
    def public(run: WorkflowRun) -> ActionRun:
        """Expose run state without the workflow definition, event payload, or secrets."""
        return ActionRun(
            id=run.id,
            workflow=run.workflow,
            name=run.name,
            sha=run.sha,
            ref=run.ref,
            actor=run.actor,
            event_name=run.event_name,
            status=ActionStatus(run.status),
            created_at=run.created_at,
            completed_at=run.completed_at,
            jobs=[ActionJob.model_validate(job) for job in run.jobs],
            error=run.error,
        )

    async def list_runs(self, owner: str, name: str, user: User | None) -> list[ActionRun]:
        """Authorize private history, advance active jobs and return recent runs."""
        repository = await self._repository(owner, name, user)
        runs = await self.store.list_runs(repository.id)
        for run in runs:
            if run.status not in TERMINAL:
                await self.scheduler.advance(repository.id, run.id)
        return [self.public(run) for run in await self.store.list_runs(repository.id)]

    async def pull_request_checks(self, owner: str, name: str, number: int, user: User | None) -> PullRequestChecks:
        """Pin checks to the current head and retain the latest delivery per workflow/event."""
        repository = await self._repository(owner, name, user)
        if self.pull_requests is None:
            raise RuntimeError("Pull request store is not configured")
        pull = await self.pull_requests.get_by_number(repository.id, number)
        sha, _ = await self.repositories.action_revision(owner, name, pull.head_branch)
        selected: dict[tuple[str, str], WorkflowRun] = {}
        for run in await self.store.runs_for_commit(repository.id, sha):
            event = workflow_event_adapter.validate_python({**run.event, "event_name": run.event_name})
            if isinstance(event, PullRequestEvent) and event.pull_request.number != number:
                continue
            key = (run.workflow, run.event_name)
            if key in selected:
                continue
            if run.status not in TERMINAL:
                await self.scheduler.advance(repository.id, run.id)
            selected[key] = run
        return PullRequestChecks(head_sha=sha, runs=[self.public(run) for run in selected.values()])

    async def cancel(self, owner: str, name: str, run_id: uuid.UUID, user: User) -> None:
        """Authorize cancellation and release job resources."""
        repository = await self._repository(owner, name, user, write=True)
        if not await self.scheduler.cancel(repository.id, run_id):
            raise HTTPException(status_code=404, detail="Workflow run not found or busy")

    async def on_push(self, owner: str, name: str, before: dict[str, str], after: dict[str, str], user: User) -> None:
        """Accept CI events only from an authenticated repository owner or administrator."""
        repository = await self._repository(owner, name, user, write=True)
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

    @staticmethod
    def _token_ids(token: str, scope: str) -> tuple[uuid.UUID, uuid.UUID]:
        """Validate purpose, expiry, and resource scope on sandbox-issued requests."""
        try:
            claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
            if claims.get("scope") != scope:
                raise HTTPException(status_code=403, detail="Invalid sandbox token scope")
            return uuid.UUID(claims["repo"]), uuid.UUID(claims["run"])
        except (jwt.InvalidTokenError, ValueError, KeyError) as exc:
            raise HTTPException(status_code=403, detail="Invalid sandbox token") from exc

    async def complete(self, token: str) -> None:
        """Advance dependent jobs immediately after a sandbox writes its exit marker."""
        repo_id, run_id = self._token_ids(token, "actions:complete")
        if not await self.scheduler.advance(repo_id, run_id):
            raise HTTPException(status_code=503, detail="Workflow is busy; retry completion callback")

    async def restore_state(self, token: str) -> bytes:
        """Serve run-scoped artifacts on demand; cache data never enters this archive."""
        repo_id, run_id = self._token_ids(token, "actions:state")
        return await self.blobs.get_current(f"actions/{repo_id}/{run_id}/state.tar.gz") or gzip.compress(bytes(1024))

    def cache_scope(self, token: str) -> uuid.UUID:
        """Validate the cache capability before accepting a bounded upload."""
        repo_id, _ = self._token_ids(token, "actions:cache")
        self._cache_service()
        return repo_id

    def _cache_service(self) -> ActionsCacheService:
        if self.cache is None:
            raise HTTPException(status_code=503, detail="Actions cache is unavailable")
        return self.cache

    async def lookup_cache(self, token: str, identity: CacheIdentity, restore_keys: list[str]) -> CacheEntry | None:
        """Find a repository cache without exposing provider credentials."""
        repo_id = self.cache_scope(token)
        return await self._cache_service().lookup(repo_id, identity, restore_keys)

    async def save_cache(self, token: str, identity: CacheIdentity, payload: bytes) -> CacheEntry:
        """Persist a bounded immutable cache entry."""
        repo_id = self.cache_scope(token)
        return await self._cache_service().save(repo_id, identity, payload)

    async def download_cache(self, token: str, payload_id: uuid.UUID) -> bytes:
        """Read only payload generations belonging to the capability's repository."""
        repo_id = self.cache_scope(token)
        payload = await self._cache_service().download(repo_id, payload_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="Cache entry expired or was evicted")
        return payload

    async def cancel_repository(self, owner: str, name: str, user: User) -> uuid.UUID:
        """Stop active sandboxes before their repository rows can be deleted."""
        repository = await self._repository(owner, name, user, write=True)
        for repo_id, run_id in await self.store.active_runs(repository.id):
            if repo_id == repository.id:
                await self.cancel(owner, name, run_id, user)
        return repository.id

    async def delete_repository_blobs(self, repo_id: uuid.UUID) -> None:
        """Remove Actions blobs after the repository deletion has committed."""
        for key in await self.blobs.list_keys(f"actions/{repo_id}/"):
            await self.blobs.delete(key)
