"""Real broker test credentials and HTTP fault controls."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx2 as httpx
from werkzeug.wrappers import Request, Response

if TYPE_CHECKING:
    from pytest_httpserver import HTTPServer

QSTASH_TOKEN = "eyJVc2VySUQiOiJkZWZhdWx0VXNlciIsIlBhc3N3b3JkIjoiZGVmYXVsdFBhc3N3b3JkIn0="
QSTASH_CURRENT_KEY = "sig_7kYjw48mhY7kAjqNGcy6cr29RJ6r"
QSTASH_NEXT_KEY = "sig_5ZB6DVzB1wjE8S6rZ7eenA8Pdnhs"
HOP_HEADERS = {"connection", "transfer-encoding", "content-length", "content-encoding", "host"}


def proxy_to(server: HTTPServer, target: str) -> None:
    """Forward original delivery bytes; pytest-httpserver owns HTTP and threading."""

    def forward(request: Request) -> Response:
        headers = {key: value for key, value in request.headers.items() if key.lower() not in HOP_HEADERS}
        response = httpx.request(
            request.method,
            target + request.full_path.removesuffix("?"),
            headers=headers,
            content=request.get_data(),
            timeout=180,
            trust_env=False,
        )
        return Response(
            response.content,
            status=response.status_code,
            headers={key: value for key, value in response.headers.items() if key.lower() not in HOP_HEADERS},
        )

    server.expect_request(re.compile(".*")).respond_with_handler(forward)


def deliveries(server: HTTPServer) -> list[tuple[Request, Response]]:
    """Read dispatch observations without depending on unrelated recovery traffic."""
    return [
        (request, response)
        for request, response in list(server.log)
        if request.path.endswith("/actions/internal/dispatch")
    ]


@dataclass
class ActionsNetwork:
    """Test-owned servers around publishing and signed callback delivery."""

    publishing: HTTPServer
    callbacks: HTTPServer
