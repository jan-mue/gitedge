"""FastAPI routes for Git smart HTTP protocol.

This module provides FastAPI routes that wrap dulwich's WSGI-based Git HTTP
server for use with blob storage and Redis backends.
"""

from __future__ import annotations

import logging
from io import BytesIO
from typing import TYPE_CHECKING, Any

from dulwich.web import GunzipFilter, HTTPGitApplication, LimitedInputFilter
from fastapi import APIRouter, Request, Response

from app.api.dependencies import BackendDep, BlobStorageClientDep
from app.services.blob_backend import BlobBackend, load_repository_from_storage, save_repository_changes_to_storage

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

    from app.clients.blob_storage import BlobStorageClient

logger = logging.getLogger(__name__)

router = APIRouter(tags=["git"])


async def _ensure_repository_loaded(backend: BlobBackend, blob_client: BlobStorageClient, repo_path: str) -> None:
    """Ensure a repository is loaded from blob storage and Redis.

    Args:
        backend: Git backend to load the repository into.
        blob_client: Blob storage client.
        repo_path: Repository path.
    """
    if backend.repository_exists(repo_path):
        return

    # Load from storage
    try:
        packs, refs = await load_repository_from_storage(blob_client, repo_path)
        if packs or refs:
            backend.load_repository_from_data(repo_path, packs, refs)
        else:
            # No existing data, create new repo
            backend.create_repository(repo_path)
    except (OSError, ValueError, TypeError) as e:
        logger.warning(f"Failed to load repository {repo_path}: {e}")
        backend.create_repository(repo_path)


async def _save_repository_changes(backend: BlobBackend, blob_client: BlobStorageClient, repo_path: str) -> None:
    """Save repository changes to blob storage and Redis.

    Args:
        backend: Git backend to read changes from.
        blob_client: Blob storage client.
        repo_path: Repository path.
    """
    changes = backend.get_repository_changes(repo_path)

    if not any(changes.values()):
        return

    await save_repository_changes_to_storage(blob_client, repo_path, changes)
    backend.clear_repository_changes(repo_path)


def _create_wsgi_environ(request: Request, body: bytes, path: str) -> dict[str, Any]:
    """Create a WSGI environ dict from a FastAPI request.

    Args:
        request: FastAPI request.
        body: Request body bytes.
        path: Path info for the request.

    Returns:
        WSGI environ dictionary.
    """
    # Build query string
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

    # Add content type and length if present
    content_type = request.headers.get("content-type")
    if content_type:
        environ["CONTENT_TYPE"] = content_type

    content_length = request.headers.get("content-length")
    if content_length:
        environ["CONTENT_LENGTH"] = content_length

    # Add HTTP headers
    for key, value in request.headers.items():
        key_upper = key.upper().replace("-", "_")
        if key_upper not in ("CONTENT_TYPE", "CONTENT_LENGTH"):
            environ[f"HTTP_{key_upper}"] = value

    return environ


async def _handle_git_request(
    request: Request,
    repo_path: str,
    backend: BlobBackend,
    blob_client: BlobStorageClient,
    service_path: str,
) -> Response:
    """Handle a Git HTTP request.

    Args:
        request: FastAPI request.
        repo_path: Repository path (e.g., "user/repo.git").
        backend: Git backend for the request.
        blob_client: Blob storage client.
        service_path: Git service path (e.g., "/info/refs").

    Returns:
        FastAPI Response.
    """
    # Ensure repository is loaded
    await _ensure_repository_loaded(backend, blob_client, repo_path)

    # Get request body
    body = await request.body()

    # Create WSGI environ
    path_info = f"/{repo_path}{service_path}"
    environ = _create_wsgi_environ(request, body, path_info)

    # Create response collector
    response_started = False
    response_status = "200 OK"
    response_headers: list[tuple[str, str]] = []
    response_body: list[bytes] = []

    def start_response(
        status: str,
        headers: list[tuple[str, str]],
        _exc_info: tuple[type[BaseException], BaseException, TracebackType] | tuple[None, None, None] | None = None,
    ) -> Callable[[bytes], object]:
        nonlocal response_started, response_status, response_headers
        response_started = True
        response_status = status
        response_headers = headers

        def write(data: bytes) -> None:
            response_body.append(data)

        return write

    # Create and call WSGI app
    wsgi_app = HTTPGitApplication(backend)
    # Apply filters
    wsgi_app_filtered = GunzipFilter(LimitedInputFilter(wsgi_app))

    # Execute WSGI app
    try:
        result = wsgi_app_filtered(environ, start_response)
        response_body.extend(result)
    except Exception:
        logger.exception("Git request failed")
        return Response(
            content="Internal error",
            status_code=500,
        )

    # Save any changes
    await _save_repository_changes(backend, blob_client, repo_path)

    # Build response
    status_code = int(response_status.split(maxsplit=1)[0])
    headers_dict = dict(response_headers)

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
    *,
    backend: BackendDep,
    blob_client: BlobStorageClientDep,
) -> Response:
    """Get repository references (used for clone/fetch discovery).

    Args:
        request: FastAPI request.
        repo_path: Repository path.
        backend: Git backend dependency.
        blob_client: Blob storage client dependency.

    Returns:
        Response with refs.
    """
    return await _handle_git_request(request, repo_path, backend, blob_client, "/info/refs")


@router.get("/{repo_path:path}/HEAD")
async def get_head(
    request: Request,
    repo_path: str,
    *,
    backend: BackendDep,
    blob_client: BlobStorageClientDep,
) -> Response:
    """Get repository HEAD.

    Args:
        request: FastAPI request.
        repo_path: Repository path.
        backend: Git backend dependency.
        blob_client: Blob storage client dependency.

    Returns:
        Response with HEAD.
    """
    return await _handle_git_request(request, repo_path, backend, blob_client, "/HEAD")


@router.get("/{repo_path:path}/objects/info/packs")
async def get_info_packs(
    request: Request,
    repo_path: str,
    *,
    backend: BackendDep,
    blob_client: BlobStorageClientDep,
) -> Response:
    """Get pack file info.

    Args:
        request: FastAPI request.
        repo_path: Repository path.
        backend: Git backend dependency.
        blob_client: Blob storage client dependency.

    Returns:
        Response with pack info.
    """
    return await _handle_git_request(request, repo_path, backend, blob_client, "/objects/info/packs")


@router.get("/{repo_path:path}/objects/{prefix:path}/{suffix}")
async def get_loose_object(
    request: Request,
    repo_path: str,
    prefix: str,
    suffix: str,
    *,
    backend: BackendDep,
    blob_client: BlobStorageClientDep,
) -> Response:
    """Get a loose object.

    Args:
        request: FastAPI request.
        repo_path: Repository path.
        prefix: Object SHA prefix (2 chars).
        suffix: Object SHA suffix (38 chars).
        backend: Git backend dependency.
        blob_client: Blob storage client dependency.

    Returns:
        Response with object data.
    """
    return await _handle_git_request(request, repo_path, backend, blob_client, f"/objects/{prefix}/{suffix}")


@router.get("/{repo_path:path}/objects/pack/{pack_file}")
async def get_pack_file(
    request: Request,
    repo_path: str,
    pack_file: str,
    *,
    backend: BackendDep,
    blob_client: BlobStorageClientDep,
) -> Response:
    """Get a pack or index file.

    Args:
        request: FastAPI request.
        repo_path: Repository path.
        pack_file: Pack file name.
        backend: Git backend dependency.
        blob_client: Blob storage client dependency.

    Returns:
        Response with pack/index data.
    """
    return await _handle_git_request(request, repo_path, backend, blob_client, f"/objects/pack/{pack_file}")


@router.post("/{repo_path:path}/git-upload-pack")
async def git_upload_pack(
    request: Request,
    repo_path: str,
    *,
    backend: BackendDep,
    blob_client: BlobStorageClientDep,
) -> Response:
    """Handle git-upload-pack (clone/fetch).

    Args:
        request: FastAPI request.
        repo_path: Repository path.
        backend: Git backend dependency.
        blob_client: Blob storage client dependency.

    Returns:
        Response with pack data.
    """
    return await _handle_git_request(request, repo_path, backend, blob_client, "/git-upload-pack")


@router.post("/{repo_path:path}/git-receive-pack")
async def git_receive_pack(
    request: Request,
    repo_path: str,
    *,
    backend: BackendDep,
    blob_client: BlobStorageClientDep,
) -> Response:
    """Handle git-receive-pack (push).

    Args:
        request: FastAPI request.
        repo_path: Repository path.
        backend: Git backend dependency.
        blob_client: Blob storage client dependency.

    Returns:
        Response with push result.
    """
    return await _handle_git_request(request, repo_path, backend, blob_client, "/git-receive-pack")
