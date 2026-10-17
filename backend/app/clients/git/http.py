"""Translate plain HTTP input to Dulwich's WSGI protocol server."""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, Any

from dulwich.web import GunzipFilter, HTTPGitApplication, LimitedInputFilter

from app.clients.git.types import GitHttpResponse

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

    from app.clients.git.blob_backend import BlobBackend
    from app.clients.git.types import GitHttpRequest


def create_wsgi_environ(request: GitHttpRequest) -> dict[str, Any]:
    """Build WSGI input using the already-decoded HTTP body length."""
    environ: dict[str, Any] = {
        "REQUEST_METHOD": request.method,
        "SCRIPT_NAME": "",
        "PATH_INFO": request.path,
        "QUERY_STRING": request.query,
        "SERVER_NAME": request.hostname,
        "SERVER_PORT": str(request.port),
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": request.scheme,
        "wsgi.input": BytesIO(request.body),
        "wsgi.errors": BytesIO(),
        "wsgi.multithread": False,
        "wsgi.multiprocess": False,
        "wsgi.run_once": True,
        "CONTENT_LENGTH": str(len(request.body)),
    }
    for key, value in request.headers.items():
        key_upper = key.upper().replace("-", "_")
        if key_upper == "CONTENT_TYPE":
            environ[key_upper] = value
        elif key_upper not in ("CONTENT_LENGTH", "TRANSFER_ENCODING"):
            environ[f"HTTP_{key_upper}"] = value
    return environ


def handle_http(backend: BlobBackend, request: GitHttpRequest) -> GitHttpResponse:
    """Run Dulwich and close its response iterator before returning buffered output."""
    response_status = "200 OK"
    response_headers: list[tuple[str, str]] = []
    body: list[bytes] = []

    def start_response(
        status: str,
        headers: list[tuple[str, str]],
        _exc_info: tuple[type[BaseException], BaseException, TracebackType] | tuple[None, None, None] | None = None,
    ) -> Callable[[bytes], object]:
        nonlocal response_status, response_headers
        response_status, response_headers = status, headers
        return body.append

    app = GunzipFilter(LimitedInputFilter(HTTPGitApplication(backend)))
    result = app(create_wsgi_environ(request), start_response)
    try:
        body.extend(result)
    finally:
        close = getattr(result, "close", None)
        if close is not None:
            close()
    return GitHttpResponse(b"".join(body), int(response_status.split(maxsplit=1)[0]), dict(response_headers))
