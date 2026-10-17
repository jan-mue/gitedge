"""Actions history, dispatch, cancellation, and scheduled reconciliation."""

import secrets
import uuid
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Response

from app.api.dependencies import ActionsServiceDep, CurrentUser, OptionalUser
from app.config import settings
from app.schemas.actions import ActionRun, WorkflowDispatch, WorkflowInfo
from app.services.actions.workflows import WorkflowError

router = APIRouter(tags=["actions"])


@router.get("/repositories/{owner}/{repo}/actions/workflows")
async def list_workflows(
    owner: str, repo: str, service: ActionsServiceDep, user: OptionalUser, response: Response, ref: str = "HEAD"
) -> list[WorkflowInfo]:
    """Discover workflows in .gitedge/workflow at a repository revision."""
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return await service.workflows(owner, repo, ref, user)
    except WorkflowError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/repositories/{owner}/{repo}/actions/runs")
async def list_runs(
    owner: str, repo: str, service: ActionsServiceDep, user: OptionalUser, response: Response
) -> list[ActionRun]:
    """Read recent runs and refresh their sandbox state."""
    response.headers["Cache-Control"] = "private, no-store"
    return await service.list_runs(owner, repo, user)


@router.post("/repositories/{owner}/{repo}/actions/dispatch", status_code=201)
async def dispatch_workflow(
    owner: str, repo: str, body: WorkflowDispatch, service: ActionsServiceDep, user: CurrentUser
) -> ActionRun:
    """Run an explicitly enabled workflow as its repository owner."""
    try:
        return await service.dispatch(owner, repo, body.workflow, body.ref, body.inputs, user)
    except WorkflowError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/repositories/{owner}/{repo}/actions/runs/{run_id}/cancel", status_code=204)
async def cancel_run(owner: str, repo: str, run_id: uuid.UUID, service: ActionsServiceDep, user: CurrentUser) -> None:
    """Cancel a run and remove its sandbox resources."""
    await service.cancel(owner, repo, run_id, user)


@router.get("/actions/reconcile", include_in_schema=False)
async def reconcile_actions(
    service: ActionsServiceDep, authorization: Annotated[str | None, Header()] = None
) -> dict[str, str]:
    """Scheduled entry point protected by Vercel's CRON_SECRET bearer token."""
    expected = f"Bearer {settings.CRON_SECRET}"
    if not settings.CRON_SECRET or not secrets.compare_digest(authorization or "", expected):
        raise HTTPException(status_code=401, detail="Invalid scheduler token")
    await service.reconcile_all()
    return {"status": "ok"}


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
    """Reconcile a completed sandbox using its short-lived, run-scoped capability."""
    await service.complete(token)
    return {"status": "accepted"}


@router.get("/meta", include_in_schema=False)
async def actions_metadata() -> dict[str, str]:
    """Expose forge metadata for actions that probe a GitHub-compatible API."""
    return {"name": "GitEdge"}
