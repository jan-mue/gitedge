"""Actions history, dispatch, cancellation, and completion callbacks."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.api.dependencies import ActionsServiceDep, OptionalRepositoryUser, RepositoryUser
from app.api.permissions import require_permission
from app.entities.users import User
from app.schemas.actions import ActionRun, PullRequestChecks, WorkflowDispatch, WorkflowInfo

router = APIRouter(tags=["actions"])


@router.get("/repositories/{owner}/{repo}/actions/workflows")
async def list_workflows(
    owner: str,
    repo: str,
    service: ActionsServiceDep,
    user: Annotated[User | None, Depends(require_permission("actions:read", user_dep=OptionalRepositoryUser))],
    response: Response,
    ref: str = "HEAD",
) -> list[WorkflowInfo]:
    """Discover workflows in .gitedge/workflow at a repository revision."""
    response.headers["Cache-Control"] = "private, no-store"
    return await service.workflows(owner, repo, ref, user)


@router.get("/repositories/{owner}/{repo}/actions/runs")
async def list_runs(
    owner: str,
    repo: str,
    service: ActionsServiceDep,
    user: Annotated[User | None, Depends(require_permission("actions:read", user_dep=OptionalRepositoryUser))],
    response: Response,
) -> list[ActionRun]:
    """Read recent runs and refresh their sandbox state."""
    response.headers["Cache-Control"] = "private, no-store"
    return await service.list_runs(owner, repo, user)


@router.get("/repositories/{owner}/{repo}/pulls/{number}/checks")
async def get_pull_request_checks(
    owner: str,
    repo: str,
    number: int,
    service: ActionsServiceDep,
    user: Annotated[User | None, Depends(require_permission("actions:read", user_dep=OptionalRepositoryUser))],
    response: Response,
) -> PullRequestChecks:
    """Return real checks for this pull request's current head commit."""
    response.headers["Cache-Control"] = "private, no-store"
    return await service.pull_request_checks(owner, repo, number, user)


@router.post("/repositories/{owner}/{repo}/actions/dispatch", status_code=201)
async def dispatch_workflow(
    owner: str,
    repo: str,
    body: WorkflowDispatch,
    service: ActionsServiceDep,
    user: Annotated[User, Depends(require_permission("actions:write", user_dep=RepositoryUser))],
) -> ActionRun:
    """Run an explicitly enabled workflow as its repository owner."""
    return await service.dispatch(owner, repo, body.workflow, body.ref, body.inputs, user)


@router.post("/repositories/{owner}/{repo}/actions/runs/{run_id}/cancel", status_code=204)
async def cancel_run(
    owner: str,
    repo: str,
    run_id: uuid.UUID,
    service: ActionsServiceDep,
    user: Annotated[User, Depends(require_permission("actions:write", user_dep=RepositoryUser))],
) -> None:
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
    """Advance a completed sandbox using its short-lived, run-scoped capability."""
    await service.complete(token)
    return {"status": "accepted"}


@router.get("/meta", include_in_schema=False)
async def actions_metadata() -> dict[str, str]:
    """Expose forge metadata for actions that probe a GitHub-compatible API."""
    return {"name": "GitEdge"}
