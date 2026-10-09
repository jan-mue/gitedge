"""FastAPI routes for Git smart HTTP protocol.

This module provides FastAPI routes that wrap dulwich's WSGI-based Git HTTP
server for use with blob storage and Redis backends.
"""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, Any

from dulwich.web import GunzipFilter, HTTPGitApplication, LimitedInputFilter
from fastapi import APIRouter, Request, Response

from app.api.dependencies import RepositoryServiceDep
from app.utils.cache_headers import CACHE_CONTROL_NO_STORE

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

    from app.services.repositories import RepositoryService

router = APIRouter(tags=["git"])

# Git endpoints whose response must never be cached by a CDN.
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
    # Pack and loose object files are addressed by content, so they are immutable.
    headers = await repository_service.cache_headers(owner, name, immutable=service_path != "/objects/info/packs")
    return headers["Cache-Control"]


def _create_wsgi_environ(request: Request, body: bytes, path: str) -> dict[str, Any]:
    """Create a WSGI environ dict from a FastAPI request.

    Args:
        request: FastAPI request.
        body: Request body bytes.
        path: Path info for the request.

    Returns:
        WSGI environ dictionary.
    """
    query_string = str(request.url.query) if request.url.query else ""

    environ: dict[str, Any] = {
        "REQUEST_METHOD": request.method,
        "SCRIPT_NAME": "",
        "PATH_INFO": path,
        "QUERY_STRING": query_string,
        "SERVER_NAME": request.url.hostname or "localhost",
        "SERVER_PORT": str(request.url.port or 80),
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": request.url.scheme,
        "wsgi.input": BytesIO(body),
        "wsgi.errors": BytesIO(),
        "wsgi.multithread": False,
        "wsgi.multiprocess": False,
        "wsgi.run_once": True,
    }

    content_type = request.headers.get("content-type")
    if content_type:
        environ["CONTENT_TYPE"] = content_type

    content_length = request.headers.get("content-length")
    if content_length:
        environ["CONTENT_LENGTH"] = content_length

    for key, value in request.headers.items():
        key_upper = key.upper().replace("-", "_")
        if key_upper not in ("CONTENT_TYPE", "CONTENT_LENGTH"):
            environ[f"HTTP_{key_upper}"] = value

    return environ


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

    body = await request.body()

    path_info = f"/{repo_path}{service_path}"
    environ = _create_wsgi_environ(request, body, path_info)

    response_status = "200 OK"
    response_headers: list[tuple[str, str]] = []
    response_body: list[bytes] = []

    def start_response(
        status: str,
        headers: list[tuple[str, str]],
        _exc_info: tuple[type[BaseException], BaseException, TracebackType] | tuple[None, None, None] | None = None,
    ) -> Callable[[bytes], object]:
        nonlocal response_status, response_headers
        response_status = status
        response_headers = headers

        def write(data: bytes) -> None:
            response_body.append(data)

        return write

    wsgi_app = HTTPGitApplication(repository_service.backend)
    wsgi_app_filtered = GunzipFilter(LimitedInputFilter(wsgi_app))

    result = wsgi_app_filtered(environ, start_response)
    response_body.extend(result)

    await repository_service.save_changes(owner, name)

    status_code = int(response_status.split(maxsplit=1)[0])
    headers_dict = dict(response_headers)
    headers_dict["Cache-Control"] = await _git_cache_control(repository_service, owner, name, service_path)

    return Response(
        content=b"".join(response_body),
        status_code=status_code,
        headers=headers_dict,
    )


# Route patterns for Git smart HTTP protocol
# These match the patterns in dulwich.web.HTTPGitApplication.services


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
