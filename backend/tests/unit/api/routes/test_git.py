from __future__ import annotations

from starlette.requests import Request

from app.api.routes.git import _create_wsgi_environ


def _make_request(
    *,
    method: str = "GET",
    query: str = "",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    scope = {
        "type": "http",
        "method": method,
        "path": "/owner/repo.git/info/refs",
        "query_string": query.encode(),
        "headers": headers or [],
        "server": ("localhost", 8000),
        "scheme": "http",
    }
    return Request(scope)


def test_create_wsgi_environ_basic() -> None:
    request = _make_request(query="service=git-upload-pack")

    environ = _create_wsgi_environ(request, b"body", "/owner/repo.git/info/refs")

    assert environ["REQUEST_METHOD"] == "GET"
    assert environ["SCRIPT_NAME"] == ""
    assert environ["PATH_INFO"] == "/owner/repo.git/info/refs"
    assert environ["QUERY_STRING"] == "service=git-upload-pack"
    assert environ["SERVER_NAME"] == "localhost"
    assert environ["SERVER_PORT"] == "8000"
    assert environ["SERVER_PROTOCOL"] == "HTTP/1.1"
    assert environ["wsgi.url_scheme"] == "http"
    assert environ["wsgi.input"].read() == b"body"
    assert environ["wsgi.multithread"] is False
    assert environ["wsgi.multiprocess"] is False
    assert environ["wsgi.run_once"] is True


def test_create_wsgi_environ_headers() -> None:
    request = _make_request(
        method="POST",
        headers=[
            (b"content-type", b"application/x-git-upload-pack-request"),
            (b"content-length", b"4"),
            (b"x-test-header", b"value"),
        ],
    )

    environ = _create_wsgi_environ(request, b"body", "/path")

    assert environ["CONTENT_TYPE"] == "application/x-git-upload-pack-request"
    assert environ["CONTENT_LENGTH"] == "4"
    assert environ["HTTP_X_TEST_HEADER"] == "value"
    assert "HTTP_CONTENT_TYPE" not in environ
    assert "HTTP_CONTENT_LENGTH" not in environ
