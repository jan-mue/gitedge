"""Test-owned HTTP faults around a real QStash development container."""

from __future__ import annotations

import threading
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, override

import httpx2 as httpx

if TYPE_CHECKING:
    from collections.abc import Generator

QSTASH_TOKEN = "eyJVc2VySUQiOiJkZWZhdWx0VXNlciIsIlBhc3N3b3JkIjoiZGVmYXVsdFBhc3N3b3JkIn0="
QSTASH_CURRENT_KEY = "sig_7kYjw48mhY7kAjqNGcy6cr29RJ6r"
QSTASH_NEXT_KEY = "sig_5ZB6DVzB1wjE8S6rZ7eenA8Pdnhs"
MAX_PROXY_BODY = 64 * 1024 * 1024
HOP_HEADERS = {"connection", "transfer-encoding", "content-length", "content-encoding", "host"}


@dataclass(frozen=True)
class DeliveryRecord:
    """A delivery observed at the network boundary."""

    path: str
    status: int
    signed: bool


class FaultProxy:
    """Forward real HTTP traffic with deterministic, single-request failures."""

    def __init__(self, target: str) -> None:
        """Keep independent fault counters for this forwarding boundary."""
        self.target = target
        self.failures: Counter[str] = Counter()
        self.records: list[DeliveryRecord] = []
        self.lock = threading.Lock()
        self.port = 0

    def fail_next(self, path_suffix: str) -> None:
        """Return one 503 for the next matching HTTP request."""
        with self.lock:
            self.failures[path_suffix] += 1

    def observed(self, path_suffix: str) -> list[DeliveryRecord]:
        """Copy matching observations without racing request threads."""
        with self.lock:
            return [record for record in self.records if record.path.endswith(path_suffix)]

    def _fail(self, path: str) -> bool:
        with self.lock:
            for suffix, remaining in self.failures.items():
                if remaining and path.endswith(suffix):
                    self.failures[suffix] -= 1
                    return True
        return False

    @contextmanager
    def running(self) -> Generator[FaultProxy]:
        """Run only for the lifetime of the owning pytest session."""
        proxy = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self._forward()

            do_POST = do_GET  # noqa: N815
            do_PUT = do_GET  # noqa: N815
            do_PATCH = do_GET  # noqa: N815
            do_DELETE = do_GET  # noqa: N815

            def _forward(self) -> None:
                length = int(self.headers.get("content-length", "0"))
                if length < 0 or length > MAX_PROXY_BODY:
                    self.send_error(413)
                    return
                body = self.rfile.read(length)
                status, payload, response_headers = 503, b"Injected network failure", {}
                if not proxy._fail(self.path):
                    headers = {key: value for key, value in self.headers.items() if key.lower() not in HOP_HEADERS}
                    with httpx.Client(timeout=180, trust_env=False) as client:
                        response = client.request(
                            self.command, f"{proxy.target}{self.path}", headers=headers, content=body
                        )
                    status, payload = response.status_code, response.content
                    response_headers = {
                        key: value for key, value in response.headers.items() if key.lower() not in HOP_HEADERS
                    }
                with proxy.lock:
                    proxy.records.append(DeliveryRecord(self.path, status, bool(self.headers.get("upstash-signature"))))
                self.send_response(status)
                for key, value in response_headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            @override
            def log_message(self, format: str, *args: object) -> None:
                pass

        with ThreadingHTTPServer(("0.0.0.0", 0), Handler) as server:
            self.port = server.server_port
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                yield self
            finally:
                server.shutdown()
                thread.join(timeout=5)


@dataclass
class ActionsNetwork:
    """Network controls for broker publishing and signed callback delivery."""

    publishing: FaultProxy | None = None
    callbacks: FaultProxy | None = None
