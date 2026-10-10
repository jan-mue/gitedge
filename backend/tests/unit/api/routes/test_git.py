from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

import pytest
from dulwich.object_format import DEFAULT_OBJECT_FORMAT
from dulwich.objects import Blob, Commit, Tree
from dulwich.pack import write_pack_objects
from dulwich.protocol import pkt_line
from starlette.requests import Request

from app.api.routes.git import _create_wsgi_environ
from app.config import settings
from app.services.blob_backend import load_repository_from_storage
from app.services.blob_repository import BlobRepository

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from tests.unit.utils.fakes import FakeStores


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


@pytest.mark.parametrize(
    "headers",
    [
        [(b"transfer-encoding", b"chunked")],
        [(b"content-length", b"100")],
        [],
    ],
)
def test_create_wsgi_environ_uses_decoded_body(headers: list[tuple[bytes, bytes]]) -> None:
    request = _make_request(method="POST", headers=headers)

    environ = _create_wsgi_environ(request, b"body", "/path")

    assert environ["CONTENT_LENGTH"] == "4"
    assert "HTTP_TRANSFER_ENCODING" not in environ
    assert environ["wsgi.input"].read() == b"body"


@pytest.mark.parametrize("chunked", [False, True])
async def test_receive_pack_persists_objects_and_refs(
    client: TestClient, fake_stores: FakeStores, *, chunked: bool
) -> None:
    blob = Blob.from_string(b"Push over smart HTTP\n")
    tree = Tree()
    tree.add(b"README.md", 0o100644, blob.id)
    commit = Commit()
    commit.tree = tree.id
    commit.author = commit.committer = b"Test <test@example.com>"
    commit.author_time = commit.commit_time = 0
    commit.author_timezone = commit.commit_timezone = 0
    commit.message = b"Initial commit\n"

    pack = BytesIO()
    write_pack_objects(pack, [blob, tree, commit], DEFAULT_OBJECT_FORMAT)
    command = b"0" * 40 + b" " + commit.id + b" refs/heads/main\0report-status\n"
    body = pkt_line(command) + pkt_line(None) + pack.getvalue()
    owner = settings.FIRST_SUPERUSER.split("@")[0]
    repo_path = f"{owner}/push.git"
    headers = {"content-type": "application/x-git-receive-pack-request"}
    if chunked:
        headers["transfer-encoding"] = "chunked"

    response = client.post(f"/{repo_path}/git-receive-pack", content=body, headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-git-receive-pack-result"
    assert response.headers["cache-control"] == "no-store"
    assert b"unpack ok\n" in response.content
    assert b"ok refs/heads/main\n" in response.content

    packs, refs = await load_repository_from_storage(fake_stores.blob, fake_stores.redis, repo_path)
    assert refs["refs/heads/main"] == commit.id
    repo = BlobRepository()
    repo.load_from_storage(packs, refs)
    assert repo[commit.id] == commit
    assert repo[tree.id] == tree
    assert repo[blob.id] == blob
