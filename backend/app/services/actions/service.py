"""Event-driven workflow scheduling with one ephemeral sandbox per expanded job."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import ValidationError

from app.entities.actions import WorkflowRun
from app.exceptions import (
    ActionsUnavailableError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    WorkflowError,
)
from app.schemas.action_dispatch import Delivery, RecoveryDelivery
from app.schemas.action_logs import JobCompletion
from app.schemas.actions import ActionJob, ActionRun, PullRequestChecks, WorkflowInfo
from app.schemas.workflow_events import DispatchEvent, PullRequestEvent, WorkflowEvent, workflow_event_adapter
from app.schemas.workflows import CompileEvent, CompileRequest
from app.services.actions.capabilities import authorize_capability, authorize_report, report_payload
from app.services.actions.dispatcher import ActionsDispatcher
from app.services.actions.events import WorkflowEvents, compile_event, snapshot_event
from app.services.actions.logs import current_attempt
from app.services.actions.runtime import merge_artifacts
from app.services.actions.scheduler import RunScheduler
from app.services.actions.workflows import instantiate_jobs, workflow_paths

if TYPE_CHECKING:
    from app.clients.actions import ActionsStore
    from app.clients.blob_storage import BlobStorageClient
    from app.clients.pull_requests import PullRequestStore
    from app.clients.qstash import ActionsQueue
    from app.clients.repositories import RepositoryStore
    from app.clients.sandboxes import AbstractSandboxClient
    from app.clients.workflow_compiler import WorkflowCompiler
    from app.entities.repositories import Repository as RepositoryEntity
    from app.entities.users import User
    from app.schemas.actions import CacheEntry, CacheIdentity
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
        queue: ActionsQueue,
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
        self.scheduler = RunScheduler(max_parallel)
        self.queue = queue
        self.events = WorkflowEvents(repositories, repository_store, pull_requests, self.trigger)
        self.dispatcher = ActionsDispatcher(store, sandbox, queue, self.scheduler, secrets or {})

    async def repository(
        self, owner: str, name: str, user: User | None = None, *, write: bool = False
    ) -> RepositoryEntity:
        """Authorize repository reads or owner-only workflow mutations."""
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        allowed = user is not None and (user.id == repository.owner_id or user.is_superuser)
        if repository.is_private and not allowed:
            raise NotFoundError("Repository not found")
        if write and not allowed:
            raise PermissionDeniedError("Only the repository owner can dispatch or cancel workflows")
        return repository

    async def workflows(self, owner: str, name: str, ref: str, user: User | None) -> list[WorkflowInfo]:
        """Discover workflow files at a requested revision."""
        await self.repository(owner, name, user)
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
        await self.repository(owner, name, user, write=True)
        runs = await self.trigger(owner, name, ref, DispatchEvent(inputs=inputs), actor=user.name, workflow=workflow)
        if not runs:
            raise WorkflowError("Workflow does not enable workflow_dispatch")
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
        event = snapshot_event(event, repository, owner, name, sha, canonical, actor)
        run_ids = []
        for path in workflow_paths(index.paths, workflow):
            raw = (await self.repositories.get_raw(owner, name, sha, path, follow_symlinks=True)).decode()
            compiled = None
            error = None
            jobs: list[ActionJob] = []
            try:
                context = compile_event(event, owner, name)
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
            run = await self.store.add_run(run, self.scheduler.advance)
            run_ids.append(run.id)
        if workflow and not run_ids:
            raise WorkflowError("Workflow not found or event is not enabled")
        if run_ids:
            await self.dispatcher.flush()
        return [self.public(run) for run in await self.store.list_runs(repository.id) if run.id in run_ids]

    @staticmethod
    def public(run: WorkflowRun) -> ActionRun:
        """Expose run state without the workflow definition, event payload, or secrets."""
        return ActionRun.model_validate(run, from_attributes=True)

    async def list_runs(self, owner: str, name: str, user: User | None) -> list[ActionRun]:
        """Return persisted history without scheduling side effects."""
        repository = await self.repository(owner, name, user)
        return [self.public(run) for run in await self.store.list_runs(repository.id)]

    async def pull_request_checks(self, owner: str, name: str, number: int, user: User | None) -> PullRequestChecks:
        """Pin checks to the current head and retain the latest delivery per workflow/event."""
        repository = await self.repository(owner, name, user)
        if self.pull_requests is None:
            raise RuntimeError("Pull request store is not configured")
        pull = await self.pull_requests.get_by_number(repository.id, number)
        sha, _ = await self.repositories.action_revision(owner, name, pull.head_branch)
        selected: dict[tuple[str, str], WorkflowRun] = {}
        for run in await self.store.list_runs(repository.id, limit=None, sha=sha):
            event = workflow_event_adapter.validate_python({**run.event, "event_name": run.event_name})
            if isinstance(event, PullRequestEvent) and event.pull_request.number != number:
                continue
            key = (run.workflow, run.event_name)
            if key in selected:
                continue
            selected[key] = run
        return PullRequestChecks(head_sha=sha, runs=[self.public(run) for run in selected.values()])

    async def cancel(self, owner: str, name: str, run_id: uuid.UUID, user: User) -> None:
        """Authorize cancellation and release job resources."""
        repository = await self.repository(owner, name, user, write=True)
        if not await self.dispatcher.cancel(repository.id, run_id):
            raise NotFoundError("Workflow run not found or busy")

    async def on_push(self, owner: str, name: str, before: dict[str, str], after: dict[str, str], user: User) -> None:
        """Compile and enqueue workflows affected by updated Git refs."""
        await self.repository(owner, name, user, write=True)
        await self.events.on_push(owner, name, before, after, user)

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
        """Compile workflows for the pull request's immutable head commit."""
        await self.events.on_pull_request(owner, name, number, head_branch, base_branch, user, action=action)

    async def delivery(self, operation: str, body: bytes, signature: str) -> None:
        """Authenticate and route a versioned QStash delivery."""
        self.queue.verify(operation, body, signature)
        try:
            parsed = (
                RecoveryDelivery.model_validate_json(body)
                if operation == "reconcile"
                else Delivery.model_validate_json(body)
            )
        except ValidationError as error:
            raise WorkflowError("Invalid Actions delivery") from error
        if isinstance(parsed, RecoveryDelivery):
            await self.dispatcher.reconcile()
        else:
            message = await self.store.message(parsed.id)
            if message and message.kind == operation:
                await self.dispatcher.deliver(message)

    async def complete(self, attempt_id: uuid.UUID, authorization: str, body: bytes) -> None:
        """Validate a pushed result and delegate its durable transition."""
        capability = await authorize_report(self.store, attempt_id, authorization, terminal=True)
        completion = report_payload(JobCompletion, body, capability)
        await self.dispatcher.complete(capability, completion)

    async def publish_state(self, attempt_id: uuid.UUID, authorization: str, payload: bytes) -> None:
        """Publish artifacts outside the lock and commit a fenced reference."""
        capability = await authorize_report(self.store, attempt_id, authorization)
        checksum = hashlib.sha256(payload).hexdigest()
        key = f"actions/{capability.repo}/{capability.run}/attempts/{attempt_id}/state-{checksum}.tar.gz"
        await self.blobs.put(key, payload)
        async with self.store.transaction(capability.run, capability.repo) as state:
            attempt = current_attempt(state, capability)
            if attempt.artifact_key and attempt.artifact_key != key:
                raise ConflictError("Attempt artifacts already published")
            attempt.artifact_key = key

    async def restore_state(self, token: str) -> bytes:
        """Restore committed artifacts without accepting stale capabilities."""
        capability = await authorize_capability(self.store, token, "actions:state")
        archives = [await self.blobs.get_current(key) for key in await self.store.artifacts(capability.run)]
        return merge_artifacts([archive for archive in archives if archive is not None])

    async def cache_scope(self, token: str) -> uuid.UUID:
        """Authorize repository cache access for the current attempt."""
        capability = await authorize_capability(self.store, token, "actions:cache")
        self._cache_service()
        return capability.repo

    def _cache_service(self) -> ActionsCacheService:
        if self.cache is None:
            raise ServiceUnavailableError("Actions cache is unavailable")
        return self.cache

    async def lookup_cache(self, token: str, identity: CacheIdentity, restore_keys: list[str]) -> CacheEntry | None:
        """Find a repository cache without exposing provider credentials."""
        repo_id = await self.cache_scope(token)
        return await self._cache_service().lookup(repo_id, identity, restore_keys)

    async def save_cache(self, token: str, identity: CacheIdentity, payload: bytes) -> CacheEntry:
        """Persist a bounded immutable cache entry."""
        repo_id = await self.cache_scope(token)
        return await self._cache_service().save(repo_id, identity, payload)

    async def download_cache(self, token: str, payload_id: uuid.UUID) -> bytes:
        """Read only payload generations belonging to the capability's repository."""
        repo_id = await self.cache_scope(token)
        payload = await self._cache_service().download(repo_id, payload_id)
        if payload is None:
            raise NotFoundError("Cache entry expired or was evicted")
        return payload

    async def cancel_repository(self, owner: str, name: str, user: User) -> uuid.UUID:
        """Stop active sandboxes before their repository rows can be deleted."""
        repository = await self.repository(owner, name, user, write=True)
        for run_id in await self.store.active_runs(repository.id):
            await self.dispatcher.cancel(repository.id, run_id)
        try:
            async with asyncio.timeout(15):
                for _ in range(150):
                    if not await self.store.active_runs(repository.id):
                        break
                    await asyncio.sleep(0.1)
                else:
                    raise ActionsUnavailableError("Repository sandbox cleanup is still pending")
        except TimeoutError as error:
            raise ActionsUnavailableError("Repository sandbox cleanup is still pending") from error
        return repository.id

    async def delete_repository_blobs(self, repo_id: uuid.UUID) -> None:
        """Remove Actions blobs after the repository deletion has committed."""
        for key in await self.blobs.list_keys(f"actions/{repo_id}/"):
            await self.blobs.delete(key)
