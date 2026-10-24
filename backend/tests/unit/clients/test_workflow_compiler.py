from typing import TYPE_CHECKING

import httpx2 as httpx
import pytest

from app.clients.workflow_compiler import MAX_COMPILER_RESPONSE, HttpWorkflowCompiler
from app.exceptions import CompilerUnavailableError, WorkflowError
from app.schemas.workflows import CompileEvent, CompileRequest
from tests.unit.utils.actions import compiled_fixture

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

REQUEST = CompileRequest(
    filename=".gitedge/workflow/basic.yaml",
    source="source is never parsed by Python",
    event=CompileEvent(name="push", ref="refs/heads/main"),
)


async def test_compiler_http_contract_uses_auth_and_checks_version(mocker: MockerFixture) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer dedicated-compiler-token"
        assert b'"version":1' in request.content
        return httpx.Response(200, json=compiled_fixture().model_dump(mode="json", by_alias=True, exclude_none=True))

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    mocker.patch("app.clients.workflow_compiler.httpx.AsyncClient", return_value=client)
    result = await HttpWorkflowCompiler("https://compiler.test/api/compile", "dedicated-compiler-token").compile(
        REQUEST
    )
    assert result == compiled_fixture()


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
    mocker: MockerFixture, status: int, payload: dict, expected: type[Exception]
) -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: httpx.Response(status, json=payload)))
    mocker.patch("app.clients.workflow_compiler.httpx.AsyncClient", return_value=client)
    with pytest.raises(expected):
        await HttpWorkflowCompiler("https://compiler.test/api/compile", "test-token").compile(REQUEST)


async def test_compiler_response_size_and_missing_configuration_are_bounded(mocker: MockerFixture) -> None:
    with pytest.raises(CompilerUnavailableError, match="must be configured"):
        await HttpWorkflowCompiler(None, None).compile(REQUEST)
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, content=b"x" * (MAX_COMPILER_RESPONSE + 1)))
    )
    mocker.patch("app.clients.workflow_compiler.httpx.AsyncClient", return_value=client)
    with pytest.raises(CompilerUnavailableError, match="4 MiB"):
        await HttpWorkflowCompiler("https://compiler.test/api/compile", "test-token").compile(REQUEST)
