"""Actions history, dispatch, cancellation, and completion callbacks."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Header, Query, Request, Response

from app.api.dependencies import ActionsServiceDep, CurrentUser, OptionalUser
from app.exceptions import PayloadTooLargeError, WorkflowError
from app.schemas.actions import ActionRun, CacheEntry, CacheIdentity, PullRequestChecks, WorkflowDispatch, WorkflowInfo
from app.services.actions.cache import STATE_LIMIT

router = APIRouter(tags=["actions"])
MAX_CACHE_KEY_LENGTH = 512
MAX_DELIVERY_BYTES = 8192


@router.get("/repositories/{owner}/{repo}/actions/workflows")
async def list_workflows(
    owner: str, repo: str, service: ActionsServiceDep, user: OptionalUser, response: Response, ref: str = "HEAD"
) -> list[WorkflowInfo]:
    """Discover workflows in .gitedge/workflow at a repository revision."""
    response.headers["Cache-Control"] = "private, no-store"
    return await service.workflows(owner, repo, ref, user)


@router.get("/repositories/{owner}/{repo}/actions/runs")
async def list_runs(
    owner: str, repo: str, service: ActionsServiceDep, user: OptionalUser, response: Response
) -> list[ActionRun]:
    """Read persisted workflow history."""
    response.headers["Cache-Control"] = "private, no-store"
    return await service.list_runs(owner, repo, user)


@router.get("/repositories/{owner}/{repo}/pulls/{number}/checks")
async def get_pull_request_checks(
    owner: str, repo: str, number: int, service: ActionsServiceDep, user: OptionalUser, response: Response
) -> PullRequestChecks:
    """Return real checks for this pull request's current head commit."""
    response.headers["Cache-Control"] = "private, no-store"
    return await service.pull_request_checks(owner, repo, number, user)


@router.post("/repositories/{owner}/{repo}/actions/dispatch", status_code=201)
async def dispatch_workflow(
    owner: str, repo: str, body: WorkflowDispatch, service: ActionsServiceDep, user: CurrentUser
) -> ActionRun:
    """Run an explicitly enabled workflow as its repository owner."""
    return await service.dispatch(owner, repo, body.workflow, body.ref, body.inputs, user)


@router.post("/repositories/{owner}/{repo}/actions/runs/{run_id}/cancel", status_code=204)
async def cancel_run(owner: str, repo: str, run_id: uuid.UUID, service: ActionsServiceDep, user: CurrentUser) -> None:
    """Cancel a run and remove its sandbox resources."""
    await service.cancel(owner, repo, run_id, user)


@router.get("/actions/state", include_in_schema=False)
async def restore_state(token: str, service: ActionsServiceDep) -> Response:
    """Download portable state after provisioning, authenticated with a scoped token."""
    return Response(
        await service.restore_state(token),
        media_type="application/gzip",
        headers={"Cache-Control": "private, no-store"},
    )


@router.post("/actions/complete", status_code=202, include_in_schema=False)
async def complete_job(token: str, service: ActionsServiceDep) -> dict[str, str]:
    """Advance a completed sandbox using its short-lived, attempt-scoped capability."""
    await service.complete(token)
    return {"status": "accepted"}


@router.get("/actions/cache/lookup", include_in_schema=False)
async def lookup_cache(
    token: str,
    response: Response,
    service: ActionsServiceDep,
    key: Annotated[str, Query(min_length=1, max_length=512)],
    version: Annotated[str, Query(max_length=512)],
    restore_keys: Annotated[list[str] | None, Query(max_length=32)] = None,
) -> CacheEntry | None:
    """Find an exact/prefix cache through a repository-scoped capability."""
    response.headers["Cache-Control"] = "private, no-store"
    prefixes = restore_keys or []
    if any(len(prefix) > MAX_CACHE_KEY_LENGTH for prefix in prefixes):
        raise WorkflowError("Cache restore key exceeds 512 characters")
    return await service.lookup_cache(token, CacheIdentity(key=key, version=version), prefixes)


@router.post("/actions/cache", include_in_schema=False)
async def save_cache(
    token: str,
    request: Request,
    service: ActionsServiceDep,
    key: Annotated[str, Query(min_length=1, max_length=512)],
    version: Annotated[str, Query(max_length=512)],
) -> CacheEntry:
    """Accept a bounded raw cache payload without multipart buffering."""
    await service.cache_scope(token)
    payload = bytearray()
    async for part in request.stream():
        if len(payload) + len(part) > STATE_LIMIT:
            raise PayloadTooLargeError("Cache exceeds 32 MiB")
        payload.extend(part)
    return await service.save_cache(token, CacheIdentity(key=key, version=version), bytes(payload))


@router.get("/actions/cache/{payload_id}", include_in_schema=False)
async def download_cache(token: str, payload_id: uuid.UUID, service: ActionsServiceDep) -> Response:
    """Download an immutable cache archive from Blob or S3."""
    return Response(
        await service.download_cache(token, payload_id),
        media_type="application/octet-stream",
        headers={"Cache-Control": "private, no-store"},
    )


@router.post("/actions/internal/{operation}", status_code=202, include_in_schema=False)
async def queue_delivery(
    operation: Literal["dispatch", "inspect", "cleanup", "reconcile"],
    request: Request,
    service: ActionsServiceDep,
    signature: Annotated[str, Header(alias="Upstash-Signature")] = "",
) -> dict[str, str]:
    """Authenticate original bytes before executing a durable command."""
    body = bytearray()
    async for part in request.stream():
        if len(body) + len(part) > MAX_DELIVERY_BYTES:
            raise PayloadTooLargeError("Actions delivery exceeds 8 KiB")
        body.extend(part)
    await service.delivery(operation, bytes(body), signature)
    return {"status": "accepted"}


@router.get("/meta", include_in_schema=False)
async def actions_metadata() -> dict[str, str]:
    """Expose forge metadata for actions that probe a GitHub-compatible API."""
    return {"name": "GitEdge"}
