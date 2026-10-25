import json
from typing import TYPE_CHECKING

import pytest

from app.clients.workflow_compiler import MAX_COMPILER_RESPONSE, HttpWorkflowCompiler
from app.exceptions import CompilerUnavailableError, WorkflowError
from app.schemas.workflows import CompileEvent, CompileRequest
from tests.unit.utils.actions import compiled_fixture

if TYPE_CHECKING:
    from respx import Router

URL = "https://compiler.test/api/compile"
REQUEST = CompileRequest(
    filename=".gitedge/workflow/basic.yaml",
    source="source is never parsed by Python",
    event=CompileEvent(name="push", ref="refs/heads/main"),
)


async def test_compiler_http_contract_uses_auth_and_checks_version(httpx2_mock: Router) -> None:
    route = httpx2_mock.post(URL, headers={"Authorization": "Bearer dedicated-compiler-token"}).respond(
        json=compiled_fixture().model_dump(mode="json", by_alias=True, exclude_none=True)
    )
    result = await HttpWorkflowCompiler(URL, "dedicated-compiler-token").compile(REQUEST)
    assert result == compiled_fixture()
    assert json.loads(route.calls.last.request.content) == REQUEST.model_dump(
        mode="json", by_alias=True, exclude_none=True
    )


@pytest.mark.parametrize(
    ("status", "payload", "expected"),
    [
        (
            422,
            {
                "error": "invalid_workflow",
                "issues": [{"filename": "ci.yaml", "line": 4, "column": 3, "message": "Invalid expression"}],
            },
            WorkflowError,
        ),
        (500, {"error": "internal_error"}, CompilerUnavailableError),
        (401, {}, CompilerUnavailableError),
        (200, {"version": 2}, CompilerUnavailableError),
        (422, {}, CompilerUnavailableError),
    ],
)
async def test_compiler_validation_is_distinct_from_internal_failures(
    httpx2_mock: Router, status: int, payload: dict, expected: type[Exception]
) -> None:
    httpx2_mock.post(URL).respond(status, json=payload)
    with pytest.raises(expected):
        await HttpWorkflowCompiler(URL, "test-token").compile(REQUEST)


async def test_compiler_response_size_and_missing_configuration_are_bounded(httpx2_mock: Router) -> None:
    with pytest.raises(CompilerUnavailableError, match="must be configured"):
        await HttpWorkflowCompiler(None, None).compile(REQUEST)
    httpx2_mock.post(URL).respond(content=b"x" * (MAX_COMPILER_RESPONSE + 1))
    with pytest.raises(CompilerUnavailableError, match="4 MiB"):
        await HttpWorkflowCompiler(URL, "test-token").compile(REQUEST)


@pytest.mark.parametrize("oversized_source", [True, False])
async def test_compiler_bounds_outbound_source_and_request_before_http(
    httpx2_mock: Router, oversized_source: bool
) -> None:
    request = REQUEST.model_copy(
        update={"source": "é" * (1024 * 1024 // 2 + 1)}
        if oversized_source
        else {"event": REQUEST.event.model_copy(update={"changed_paths": ["file"] * 400000})}
    )
    with pytest.raises(WorkflowError, match="exceeds"):
        await HttpWorkflowCompiler(URL, "test-token").compile(request)
    assert not httpx2_mock.calls
