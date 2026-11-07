"""FastAPI routes for Git smart HTTP protocol.

Routes translate web requests to the selected Git engine's plain HTTP interface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status

from app.api.dependencies import ActionsServiceDep, GitUser, RepositoryServiceDep
from app.api.permissions import require_permission
from app.clients.git.types import GitHttpRequest
from app.utils.cache_headers import CACHE_CONTROL_NO_STORE

if TYPE_CHECKING:
    from app.services.repositories import RepositoryService

router = APIRouter(tags=["git"])


def git_discovery_permission(request: Request) -> str:
    """Require write access when advertising receive-pack to a pushing client."""
    return "git:write" if request.query_params.get("service") == "git-receive-pack" else "git:read"


_NO_STORE_PATHS = frozenset({"/info/refs", "/HEAD", "/git-upload-pack", "/git-receive-pack"})


async def _git_cache_control(repository_service: RepositoryService, owner: str, name: str, service_path: str) -> str:
    """Pick a Cache-Control value for a Git HTTP response.

    Args:
        repository_service: Repository service that resolves repository privacy.
        owner: Repository owner.
        name: Repository name.
        service_path: Git service path (e.g. "/info/refs").

    Returns:
        The Cache-Control header value.
    """
    if service_path in _NO_STORE_PATHS:
        return CACHE_CONTROL_NO_STORE
    headers = await repository_service.cache_headers(owner, name, immutable=service_path != "/objects/info/packs")
    return headers["Cache-Control"]


async def _handle_git_request(
    request: Request,
    repo_path: str,
    service_path: str,
    repository_service: RepositoryService,
) -> Response:
    """Handle a Git HTTP request.

    Args:
        request: FastAPI request.
        repo_path: Repository path (e.g., "user/repo.git").
        service_path: Git service path (e.g., "/info/refs").
        repository_service: Repository service.

    Returns:
        FastAPI Response.
    """
    repo_path = repo_path.strip("/")
    owner, _, name = repo_path.removesuffix(".git").partition("/")
    await repository_service.ensure_loaded(owner, name)

    result = await repository_service.git.handle_http(
        GitHttpRequest(
            method=request.method,
            path=f"/{repo_path}{service_path}",
            query=str(request.url.query),
            headers=dict(request.headers),
            body=await request.body(),
            scheme=request.url.scheme,
            hostname=request.url.hostname or "localhost",
            port=request.url.port or 80,
        )
    )
    await repository_service.save_changes(owner, name)
    headers = dict(result.headers)
    headers["Cache-Control"] = await _git_cache_control(repository_service, owner, name, service_path)
    return Response(content=result.body, status_code=result.status, headers=headers)


@router.get(
    "/{owner}/{repo}/info/refs",
    include_in_schema=False,
    dependencies=[
        Depends(require_permission(git_discovery_permission, user_dep=GitUser, challenge='Basic realm="GitEdge"'))
    ],
)
@router.get(
    "/{owner}/{repo}.git/info/refs",
    dependencies=[
        Depends(require_permission(git_discovery_permission, user_dep=GitUser, challenge='Basic realm="GitEdge"'))
    ],
)
async def get_info_refs(
    request: Request,
    owner: str,
    repo: str,
    repository_service: RepositoryServiceDep,
) -> Response:
    """Get repository references (used for clone/fetch discovery).

    Args:
        request: FastAPI request.
        owner: Repository owner.
        repo: Repository name.
        repository_service: Repository service.

    Returns:
        Response with refs.
    """
    return await _handle_git_request(request, f"{owner}/{repo}.git", "/info/refs", repository_service)


@router.get(
    "/{owner}/{repo}/HEAD",
    include_in_schema=False,
    dependencies=[Depends(require_permission("git:read", user_dep=GitUser, challenge='Basic realm="GitEdge"'))],
)
@router.get(
    "/{owner}/{repo}.git/HEAD",
    dependencies=[Depends(require_permission("git:read", user_dep=GitUser, challenge='Basic realm="GitEdge"'))],
)
async def get_head(
    request: Request,
    owner: str,
    repo: str,
    repository_service: RepositoryServiceDep,
) -> Response:
    """Get repository HEAD.

    Args:
        request: FastAPI request.
        owner: Repository owner.
        repo: Repository name.
        repository_service: Repository service.

    Returns:
        Response with HEAD.
    """
    return await _handle_git_request(request, f"{owner}/{repo}.git", "/HEAD", repository_service)


@router.get(
    "/{owner}/{repo}/objects/info/packs",
    include_in_schema=False,
    dependencies=[Depends(require_permission("git:read", user_dep=GitUser, challenge='Basic realm="GitEdge"'))],
)
@router.get(
    "/{owner}/{repo}.git/objects/info/packs",
    dependencies=[Depends(require_permission("git:read", user_dep=GitUser, challenge='Basic realm="GitEdge"'))],
)
async def get_info_packs(
    request: Request,
    owner: str,
    repo: str,
    repository_service: RepositoryServiceDep,
) -> Response:
    """Get pack file info.

    Args:
        request: FastAPI request.
        owner: Repository owner.
        repo: Repository name.
        repository_service: Repository service.

    Returns:
        Response with pack info.
    """
    return await _handle_git_request(request, f"{owner}/{repo}.git", "/objects/info/packs", repository_service)


@router.get(
    "/{owner}/{repo}/objects/{prefix:path}/{suffix}",
    include_in_schema=False,
    dependencies=[Depends(require_permission("git:read", user_dep=GitUser, challenge='Basic realm="GitEdge"'))],
)
@router.get(
    "/{owner}/{repo}.git/objects/{prefix:path}/{suffix}",
    dependencies=[Depends(require_permission("git:read", user_dep=GitUser, challenge='Basic realm="GitEdge"'))],
)
async def get_loose_object(
    request: Request,
    owner: str,
    repo: str,
    prefix: str,
    suffix: str,
    repository_service: RepositoryServiceDep,
) -> Response:
    """Get a loose object.

    Args:
        request: FastAPI request.
        owner: Repository owner.
        repo: Repository name.
        prefix: Object SHA prefix (2 chars).
        suffix: Object SHA suffix (38 chars).
        repository_service: Repository service.

    Returns:
        Response with object data.
    """
    return await _handle_git_request(request, f"{owner}/{repo}.git", f"/objects/{prefix}/{suffix}", repository_service)


@router.get(
    "/{owner}/{repo}/objects/pack/{pack_file}",
    include_in_schema=False,
    dependencies=[Depends(require_permission("git:read", user_dep=GitUser, challenge='Basic realm="GitEdge"'))],
)
@router.get(
    "/{owner}/{repo}.git/objects/pack/{pack_file}",
    dependencies=[Depends(require_permission("git:read", user_dep=GitUser, challenge='Basic realm="GitEdge"'))],
)
async def get_pack_file(
    request: Request,
    owner: str,
    repo: str,
    pack_file: str,
    repository_service: RepositoryServiceDep,
) -> Response:
    """Get a pack or index file.

    Args:
        request: FastAPI request.
        owner: Repository owner.
        repo: Repository name.
        pack_file: Pack file name.
        repository_service: Repository service.

    Returns:
        Response with pack/index data.
    """
    return await _handle_git_request(request, f"{owner}/{repo}.git", f"/objects/pack/{pack_file}", repository_service)


@router.post(
    "/{owner}/{repo}/git-upload-pack",
    include_in_schema=False,
    dependencies=[Depends(require_permission("git:read", user_dep=GitUser, challenge='Basic realm="GitEdge"'))],
)
@router.post(
    "/{owner}/{repo}.git/git-upload-pack",
    dependencies=[Depends(require_permission("git:read", user_dep=GitUser, challenge='Basic realm="GitEdge"'))],
)
async def git_upload_pack(
    request: Request,
    owner: str,
    repo: str,
    repository_service: RepositoryServiceDep,
) -> Response:
    """Handle git-upload-pack (clone/fetch).

    Args:
        request: FastAPI request.
        owner: Repository owner.
        repo: Repository name.
        repository_service: Repository service.

    Returns:
        Response with pack data.
    """
    return await _handle_git_request(request, f"{owner}/{repo}.git", "/git-upload-pack", repository_service)


@router.post(
    "/{owner}/{repo}/git-receive-pack",
    include_in_schema=False,
    dependencies=[Depends(require_permission("git:write", user_dep=GitUser, challenge='Basic realm="GitEdge"'))],
)
@router.post(
    "/{owner}/{repo}.git/git-receive-pack",
    dependencies=[Depends(require_permission("git:write", user_dep=GitUser, challenge='Basic realm="GitEdge"'))],
)
async def git_receive_pack(
    request: Request,
    owner: str,
    repo: str,
    repository_service: RepositoryServiceDep,
    actions: ActionsServiceDep,
    user: GitUser,
    background_tasks: BackgroundTasks,
) -> Response:
    """Handle git-receive-pack (push).

    Args:
        request: FastAPI request.
        owner: Repository owner.
        repo: Repository name.
        repository_service: Repository service.
        actions: Workflow orchestration service.
        user: Authenticated event actor, when provided.
        background_tasks: On-demand event dispatch after the push is persisted.

    Returns:
        Response with push result.
    """
    await repository_service.ensure_loaded(owner, repo)
    before = await repository_service.action_refs(owner, repo) if user else {}
    response = await _handle_git_request(request, f"{owner}/{repo}.git", "/git-receive-pack", repository_service)
    if user and response.status_code == status.HTTP_200_OK:
        after = await repository_service.action_refs(owner, repo)
        background_tasks.add_task(actions.on_push, owner, repo, before, after, user)
    return response
