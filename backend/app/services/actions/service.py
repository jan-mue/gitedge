"""Event-driven workflow scheduling with one ephemeral sandbox per expanded job."""

from __future__ import annotations

import asyncio
import json
import logging
import tarfile
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import jwt
from fastapi import HTTPException

from app.clients.sandboxes import SandboxError
from app.config import settings
from app.entities.actions import WorkflowRun
from app.entities.issues import IssueState
from app.entities.principals import PrincipalType
from app.schemas.actions import ActionJob, ActionRun, ActionStatus, PullRequestChecks, WorkflowInfo
from app.services.actions.cache import MAX_CACHE_ENTRIES, STATE_LIMIT, cache_blobs, restore_archive
from app.services.actions.runtime import finish_job, redact, update_logs
from app.services.actions.workflows import (
    WORKFLOW_PREFIX,
    WorkflowError,
    matches_event,
    parse_workflow,
    plan_jobs,
    workflow_info,
)
from app.utils import security

if TYPE_CHECKING:
    from typing import Any

    from app.clients.actions import ActionsStore
    from app.clients.blob_storage import BlobStorageClient
    from app.clients.pull_requests import PullRequestStore
    from app.clients.repositories import RepositoryStore
    from app.clients.sandboxes import AbstractSandboxClient
    from app.entities.repositories import Repository as RepositoryEntity
    from app.entities.users import User
    from app.services.repositories import RepositoryService

logger = logging.getLogger(__name__)

TERMINAL = {ActionStatus.SUCCESS, ActionStatus.FAILURE, ActionStatus.SKIPPED, ActionStatus.CANCELLED}


class ActionsService:
    """Advance persisted runs from workflow events and sandbox completion callbacks."""

    def __init__(
        self,
        store: ActionsStore,
        repositories: RepositoryService,
        repository_store: RepositoryStore,
        blobs: BlobStorageClient,
        providers: dict[str, AbstractSandboxClient],
        *,
        provider: str,
        max_timeout: int,
        max_parallel: int,
        secrets: dict[str, dict[str, str]] | None = None,
        pull_requests: PullRequestStore | None = None,
    ) -> None:
        """Inject data access and sandbox clients; keep provider policy out of workflows."""
        self.store = store
        self.repositories = repositories
        self.repository_store = repository_store
        self.blobs = blobs
        self.providers = providers
        self.provider = provider
        self.max_timeout = max_timeout
        self.max_parallel = max_parallel
        self.secrets = secrets or {}
        self.pull_requests = pull_requests

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
        for path in index.paths:
            if (
                path.startswith(WORKFLOW_PREFIX)
                and "/" not in path[len(WORKFLOW_PREFIX) :]
                and path.endswith((".yml", ".yaml"))
            ):
                raw = await self.repositories.get_raw(owner, name, sha, path)
                definition = parse_workflow(raw.decode())
                result.append(workflow_info(path, definition))
        return result

    async def dispatch(
        self, owner: str, name: str, workflow: str, ref: str, inputs: dict[str, str], user: User
    ) -> ActionRun:
        """Authorize a manual dispatch before provisioning any job resources."""
        await self._repository(owner, name, user, write=True)
        runs = await self.trigger(
            owner, name, ref, "workflow_dispatch", {"inputs": inputs}, actor=user.name, workflow=workflow
        )
        if not runs:
            raise HTTPException(status_code=422, detail="Workflow does not enable workflow_dispatch")
        return runs[0]

    async def trigger(
        self,
        owner: str,
        name: str,
        ref: str,
        event_name: str,
        event: dict[str, Any],
        *,
        actor: str,
        workflow: str | None = None,
        event_key: str | None = None,
    ) -> list[ActionRun]:
        """Snapshot triggered workflows at the exact event commit; deduplicate deliveries."""
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        initial_index = await self.repositories.get_file_index(owner, name, ref)
        if not workflow and not any(path.startswith(WORKFLOW_PREFIX) for path in initial_index.paths):
            return []
        sha, canonical = await self.repositories.action_revision(owner, name, ref)
        index = await self.repositories.get_file_index(owner, name, sha)
        event = {
            **event,
            "ref": event.get("ref", canonical),
            "after": sha,
            "repository": {
                "full_name": f"{owner}/{name}",
                "name": name,
                "default_branch": repository.default_branch,
                "private": repository.is_private,
                "html_url": f"{settings.ACTIONS_SERVER_URL}/{owner}/{name}",
                "clone_url": f"{settings.ACTIONS_SERVER_URL}/{owner}/{name}.git",
                "owner": {
                    "login": owner,
                    "name": repository.owner.display_name or owner,
                    "type": "Organization" if repository.owner.principal_type == PrincipalType.ORGANIZATION else "User",
                },
            },
            "sender": {"login": actor, "type": "User"},
        }
        run_ids = []
        for path in index.paths:
            if (
                not path.startswith(WORKFLOW_PREFIX)
                or "/" in path[len(WORKFLOW_PREFIX) :]
                or not path.endswith((".yml", ".yaml"))
                or (workflow and workflow != path)
            ):
                continue
            raw = (await self.repositories.get_raw(owner, name, sha, path)).decode()
            info = None
            error = None
            jobs: list[ActionJob] = []
            try:
                definition = parse_workflow(raw)
                if not matches_event(definition, event_name, event):
                    continue
                info = workflow_info(path, definition)
                jobs = plan_jobs(definition, self.max_timeout)
            except (WorkflowError, ValueError, TypeError, KeyError) as exc:
                logger.warning("Invalid workflow %s in %s/%s: %s", path, owner, name, exc)
                error = str(exc)
            run = WorkflowRun(
                id=uuid.uuid4(),
                repo_id=repository.id,
                workflow=path,
                definition=raw,
                name=info.name if info else path,
                sha=sha,
                ref=str(event["ref"]),
                actor=actor,
                event_name=event_name,
                event_key=event_key or uuid.uuid4().hex,
                event=event,
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
            await self.advance_run(repository.id, run_id)
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
        """Authorize private history, then advance_run active jobs and return recent runs."""
        repository = await self._repository(owner, name, user)
        runs = await self.store.list_runs(repository.id)
        for run in runs:
            if run.status not in TERMINAL:
                await self.advance_run(repository.id, run.id)
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
            if run.event_name == "pull_request" and run.event.get("pull_request", {}).get("number") != number:
                continue
            key = (run.workflow, run.event_name)
            if key in selected:
                continue
            if run.status not in TERMINAL:
                await self.advance_run(repository.id, run.id)
            selected[key] = run
        return PullRequestChecks(head_sha=sha, runs=[self.public(run) for run in selected.values()])

    async def cancel(self, owner: str, name: str, run_id: uuid.UUID, user: User) -> None:
        """Cancel queued/running jobs and destroy their resources."""
        repository = await self._repository(owner, name, user, write=True)
        async with self.store.locked(repository.id, run_id) as run:
            if run is None:
                raise HTTPException(status_code=404, detail="Workflow run not found or busy")
            if run.status in TERMINAL:
                return
            jobs = [ActionJob.model_validate(job) for job in run.jobs]
            provider = self.providers[run.provider]
            for job in jobs:
                if job.status not in TERMINAL:
                    job.status = ActionStatus.CANCELLED
                    job.completed_at = datetime.now(UTC)
                if job.sandbox:
                    await provider.delete(job.sandbox)
                    job.sandbox = None
            run.status = "cancelled"
            run.completed_at = datetime.now(UTC)
            run.jobs = [job.model_dump(mode="json") for job in jobs]

    async def advance_run(self, repo_id: uuid.UUID, run_id: uuid.UUID) -> bool:  # noqa: PLR0912
        """Atomically collect finished jobs, clean resources, and schedule ready variants."""
        async with self.store.locked(repo_id, run_id) as run:
            if run is None:
                return False
            if run.status in TERMINAL:
                return True
            run.updated_at = datetime.now(UTC)
            provider = self.providers[run.provider]
            secret_values = self.secrets.get(str(repo_id), {})
            jobs = [ActionJob.model_validate(job) for job in run.jobs]
            for job in jobs:
                if not job.sandbox:
                    continue
                try:
                    if job.status == ActionStatus.RUNNING:
                        snapshot = await provider.inspect(job.sandbox)
                        update_logs(job, snapshot.files.get("log.jsonl", b""), secret_values)
                        if not snapshot.running or "exit-code" in snapshot.files:
                            finish_job(job, snapshot.files, secret_values)
                            state = snapshot.files.get("state.tar.gz")
                            if state:
                                await self.blobs.put(f"actions/{repo_id}/{run.id}/jobs/{job.id}.tar.gz", state)
                                await self.blobs.put(f"actions/{repo_id}/{run.id}/state.tar.gz", state)
                                cache = snapshot.files.get("cache.tar.gz")
                                if job.status == ActionStatus.SUCCESS and cache:
                                    try:
                                        for identifier, data in cache_blobs(cache).items():
                                            await self.blobs.put(f"actions/{repo_id}/cache/{identifier}.tar.gz", data)
                                    except (ValueError, KeyError, OSError, tarfile.TarError) as exc:
                                        job.status = ActionStatus.FAILURE
                                        job.error = "Sandbox produced an invalid cache archive"
                                        logger.warning(
                                            "Invalid cache archive for job %s: %s", job.id, type(exc).__name__
                                        )
                    if job.status in TERMINAL:
                        await provider.delete(job.sandbox)
                        job.sandbox = None
                except SandboxError as exc:
                    logger.exception("Sandbox state collection failed for job %s", job.id)
                    job.status = ActionStatus.FAILURE
                    job.completed_at = datetime.now(UTC)
                    job.error = redact(str(exc), secret_values)
                    # Keep the handle so cleanup is retried on the next invocation.
            queued = [job for job in jobs if job.status == ActionStatus.QUEUED]
            while queued and sum(other.status == ActionStatus.RUNNING for other in jobs) < self.max_parallel:
                job = next(
                    (
                        candidate
                        for candidate in queued
                        if all(parent.status in TERMINAL for parent in jobs if parent.key in candidate.needs)
                    ),
                    None,
                )
                if job is None:
                    break
                queued.remove(job)
                job.started_at = datetime.now(UTC)
                job.sandbox = f"gitedge-job-{job.id}"
                job.status = ActionStatus.RUNNING
                try:
                    files = await self._job_files(run, job, jobs, secret_values)
                    provision_start = time.perf_counter()
                    await provider.start(job.sandbox, files, job.timeout_seconds)
                    job.provisioning_ms = round((time.perf_counter() - provision_start) * 1000, 2)
                except SandboxError as exc:
                    logger.exception("Sandbox launch failed for job %s", job.id)
                    job.status = ActionStatus.FAILURE
                    job.completed_at = datetime.now(UTC)
                    job.error = redact(str(exc), secret_values)
                    try:
                        await provider.delete(job.sandbox)
                        job.sandbox = None
                    except SandboxError:
                        logger.exception("Sandbox cleanup failed after launch for job %s", job.id)
            run.jobs = [job.model_dump(mode="json") for job in jobs]
            if all(job.status in TERMINAL and job.sandbox is None for job in jobs):
                run.status = (
                    "failure"
                    if any(job.status == ActionStatus.FAILURE and not job.continue_on_error for job in jobs)
                    else "success"
                )
                run.completed_at = datetime.now(UTC)
            else:
                run.status = "running"
        return True

    async def _job_files(
        self, run: WorkflowRun, job: ActionJob, jobs: list[ActionJob], secrets: dict[str, str]
    ) -> dict[str, bytes]:
        needs = {}
        for key in job.needs:
            parents = [other for other in jobs if other.key == key]
            status = next(
                (
                    status
                    for status in ("failure", "cancelled", "skipped")
                    if any(parent.status == status and not parent.continue_on_error for parent in parents)
                ),
                "success",
            )
            needs[key] = {
                "result": status,
                "outputs": {key: value for parent in parents for key, value in parent.outputs.items()},
            }
        repository = run.event["repository"]["full_name"]
        env = {
            "GITHUB_RUN_ID": str(run.id.int & ((1 << 63) - 1)),
            "GITHUB_RUN_NUMBER": str(int(run.created_at.timestamp())),
            "GITHUB_REPOSITORY": repository,
            "GITHUB_REPOSITORY_OWNER": repository.split("/")[0],
            "GITHUB_REF": run.ref,
            "GITHUB_SHA": run.sha,
        }
        read_token = jwt.encode(
            {
                "sub": "actions",
                "repo": str(run.repo_id),
                "scope": "git:read",
                "exp": datetime.now(UTC) + timedelta(seconds=job.timeout_seconds + 60),
            },
            settings.SECRET_KEY,
            algorithm=security.ALGORITHM,
        )
        env.update(
            {
                "GITHUB_SERVER_URL": settings.ACTIONS_SERVER_URL,
                "GITHUB_API_URL": settings.ACTIONS_SERVER_URL + "/api/v1",
            }
        )
        secrets = {**secrets, "GITHUB_TOKEN": read_token}
        config = {
            "dispatched_at_ms": time.time() * 1000,
            "workflow": run.definition,
            "job": job.key,
            "timeout_seconds": job.timeout_seconds,
            "matrix": job.matrix,
            "needs": needs,
            "event_name": run.event_name,
            "event": run.event,
            "actor": run.actor,
            "env": env,
            "secrets": secrets,
        }
        for purpose, field in (("state", "restore_url"), ("complete", "complete_url")):
            token = jwt.encode(
                {
                    "repo": str(run.repo_id),
                    "run": str(run.id),
                    "scope": f"actions:{purpose}",
                    "exp": datetime.now(UTC) + timedelta(seconds=job.timeout_seconds + 60),
                },
                settings.SECRET_KEY,
                algorithm=security.ALGORITHM,
            )
            config[field] = f"{settings.ACTIONS_SERVER_URL}/api/v1/actions/{purpose}?token={token}"
        return {"input.json": json.dumps(config).encode()}

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
                "push",
                {"ref": ref, "before": old or "0" * 40, "changed_paths": paths},
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
        if not any(path.startswith(WORKFLOW_PREFIX) for path in index.paths):
            return
        sha, _ = await self.repositories.action_revision(owner, name, head_branch)
        base_sha, _ = await self.repositories.action_revision(owner, name, base_branch)
        comparison = await self.repositories.compare(owner, name, base_sha, sha, include_diff=False)
        event = {
            "action": action,
            "number": number,
            "ref": f"refs/heads/{head_branch}",
            "changed_paths": [file.path for file in comparison.files],
            "pull_request": {
                "number": number,
                "head": {"ref": head_branch, "sha": sha},
                "base": {"ref": base_branch, "sha": base_sha},
            },
        }
        await self.trigger(
            owner, name, sha, "pull_request", event, actor=user.name, event_key=f"pr:{number}:{action}:{sha}"
        )

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
        if not await self.advance_run(repo_id, run_id):
            raise HTTPException(status_code=503, detail="Workflow is busy; retry completion callback")

    async def restore_state(self, token: str) -> bytes:
        """Serve a repository-scoped state archive to a newly provisioned sandbox."""
        repo_id, run_id = self._token_ids(token, "actions:state")
        state = await self.blobs.get_current(
            f"actions/{repo_id}/{run_id}/state.tar.gz"
        ) or await self.blobs.get_current(f"actions/{repo_id}/cache.tar.gz")
        # Independent cache-entry blobs avoid last-writer-wins loss between jobs.
        keys = (await self.blobs.list_keys(f"actions/{repo_id}/cache/"))[:MAX_CACHE_ENTRIES]
        archives: list[bytes] = []
        budget = STATE_LIMIT
        for offset in range(0, len(keys), 4):
            batch = await asyncio.gather(*(self.blobs.get_current(key) for key in keys[offset : offset + 4]))
            for data in batch:
                if data and len(data) <= budget:
                    archives.append(data)
                    budget -= len(data)
            if budget == 0:
                break
        return restore_archive(state, archives)

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
