"""FastAPI routes for Git smart HTTP protocol.

Routes translate web requests to the selected Git engine's plain HTTP interface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Request, Response

from app.api.dependencies import RepositoryServiceDep
from app.clients.git.types import GitHttpRequest
from app.utils.cache_headers import CACHE_CONTROL_NO_STORE

if TYPE_CHECKING:
    from app.services.repositories import RepositoryService

router = APIRouter(tags=["git"])

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


@router.get("/{repo_path:path}/info/refs")
async def get_info_refs(
    request: Request,
    repo_path: str,
    repository_service: RepositoryServiceDep,
) -> Response:
    """Get repository references (used for clone/fetch discovery).

    Args:
        request: FastAPI request.
        repo_path: Repository path.
        repository_service: Repository service.

    Returns:
        Response with refs.
    """
    return await _handle_git_request(request, repo_path, "/info/refs", repository_service)


@router.get("/{repo_path:path}/HEAD")
async def get_head(
    request: Request,
    repo_path: str,
    repository_service: RepositoryServiceDep,
) -> Response:
    """Get repository HEAD.

    Args:
        request: FastAPI request.
        repo_path: Repository path.
        repository_service: Repository service.

    Returns:
        Response with HEAD.
    """
    return await _handle_git_request(request, repo_path, "/HEAD", repository_service)


@router.get("/{repo_path:path}/objects/info/packs")
async def get_info_packs(
    request: Request,
    repo_path: str,
    repository_service: RepositoryServiceDep,
) -> Response:
    """Get pack file info.

    Args:
        request: FastAPI request.
        repo_path: Repository path.
        repository_service: Repository service.

    Returns:
        Response with pack info.
    """
    return await _handle_git_request(request, repo_path, "/objects/info/packs", repository_service)


@router.get("/{repo_path:path}/objects/{prefix:path}/{suffix}")
async def get_loose_object(
    request: Request,
    repo_path: str,
    prefix: str,
    suffix: str,
    repository_service: RepositoryServiceDep,
) -> Response:
    """Get a loose object.

    Args:
        request: FastAPI request.
        repo_path: Repository path.
        prefix: Object SHA prefix (2 chars).
        suffix: Object SHA suffix (38 chars).
        repository_service: Repository service.

    Returns:
        Response with object data.
    """
    return await _handle_git_request(request, repo_path, f"/objects/{prefix}/{suffix}", repository_service)


@router.get("/{repo_path:path}/objects/pack/{pack_file}")
async def get_pack_file(
    request: Request,
    repo_path: str,
    pack_file: str,
    repository_service: RepositoryServiceDep,
) -> Response:
    """Get a pack or index file.

    Args:
        request: FastAPI request.
        repo_path: Repository path.
        pack_file: Pack file name.
        repository_service: Repository service.

    Returns:
        Response with pack/index data.
    """
    return await _handle_git_request(request, repo_path, f"/objects/pack/{pack_file}", repository_service)


@router.post("/{repo_path:path}/git-upload-pack")
async def git_upload_pack(
    request: Request,
    repo_path: str,
    repository_service: RepositoryServiceDep,
) -> Response:
    """Handle git-upload-pack (clone/fetch).

    Args:
        request: FastAPI request.
        repo_path: Repository path.
        repository_service: Repository service.

    Returns:
        Response with pack data.
    """
    return await _handle_git_request(request, repo_path, "/git-upload-pack", repository_service)


@router.post("/{repo_path:path}/git-receive-pack")
async def git_receive_pack(
    request: Request,
    repo_path: str,
    repository_service: RepositoryServiceDep,
) -> Response:
    """Handle git-receive-pack (push).

    Args:
        request: FastAPI request.
        repo_path: Repository path.
        repository_service: Repository service.

    Returns:
        Response with push result.
    """
    return await _handle_git_request(request, repo_path, "/git-receive-pack", repository_service)
