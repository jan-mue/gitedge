"""Authenticated, bounded HTTP access to the on-demand Bun compiler."""

from __future__ import annotations

from abc import ABC, abstractmethod
from http import HTTPStatus
from typing import TYPE_CHECKING, override

import httpx2 as httpx
from pydantic import ValidationError

from app.exceptions import CompilerUnavailableError, WorkflowError
from app.schemas.workflows import CompiledWorkflow, CompilerFailure

if TYPE_CHECKING:
    from app.schemas.workflows import CompileRequest

MAX_COMPILER_RESPONSE = 4 * 1024 * 1024
MAX_COMPILER_REQUEST = 2 * 1024 * 1024
MAX_WORKFLOW_SOURCE = 1024 * 1024


class WorkflowCompiler(ABC):
    """Compile source without implementing the workflow language in Python."""

    @abstractmethod
    async def compile(self, request: CompileRequest) -> CompiledWorkflow:
        """Return the validated compiler IR or a classified error."""


class HttpWorkflowCompiler(WorkflowCompiler):
    """Use the same HTTP contract for local Bun and the Vercel Function."""

    def __init__(self, url: str | None, token: str | None) -> None:
        """Inject operator-controlled endpoint and dedicated credentials."""
        self.url = url
        self.token = token

    @override
    async def compile(self, request: CompileRequest) -> CompiledWorkflow:
        """Bound response size and distinguish workflow rejection from outages."""
        if not self.url or not self.token:
            raise CompilerUnavailableError("ACTIONS_COMPILER_URL and ACTIONS_COMPILER_TOKEN must be configured")
        if len(request.source.encode()) > MAX_WORKFLOW_SOURCE:
            raise WorkflowError("Workflow source exceeds 1 MiB")
        body = request.model_dump_json(by_alias=True, exclude_none=True).encode()
        if len(body) > MAX_COMPILER_REQUEST:
            raise WorkflowError("Compiler request exceeds 2 MiB")
        try:
            async with (
                httpx.AsyncClient(timeout=httpx.Timeout(10, connect=3)) as client,
                client.stream(
                    "POST",
                    self.url,
                    headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
                    content=body,
                ) as response,
            ):
                payload = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(payload) + len(chunk) > MAX_COMPILER_RESPONSE:
                        raise CompilerUnavailableError("Compiler response exceeds 4 MiB")
                    payload.extend(chunk)
                if response.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE:
                    raise WorkflowError("Compiler request exceeds 2 MiB")
                if response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY:
                    failure = CompilerFailure.model_validate_json(payload)
                    raise WorkflowError(
                        "\n".join(
                            f"{issue.filename or request.filename}:{issue.line or '?'}:{issue.column or '?'}: {issue.message}"
                            for issue in failure.issues
                        )
                    )
                if response.status_code != HTTPStatus.OK:
                    raise CompilerUnavailableError(f"Compiler returned HTTP {response.status_code}")
                return CompiledWorkflow.model_validate_json(payload)
        except httpx.HTTPError as exc:
            raise CompilerUnavailableError("Workflow compiler request failed") from exc
        except (ValidationError, ValueError) as exc:
            if isinstance(exc, WorkflowError):
                raise
            raise CompilerUnavailableError("Compiler returned an invalid response") from exc
