import json
from typing import TYPE_CHECKING

import pytest
from vercel.oidc import VercelOidcTokenError

from app.clients.workflow_compiler import MAX_COMPILER_RESPONSE, HttpWorkflowCompiler
from app.config import settings
from app.exceptions import CompilerUnavailableError, WorkflowError
from app.schemas.workflows import CompileEvent, CompileRequest
from tests.unit.utils.actions import compiled_fixture

if TYPE_CHECKING:
    from pytest_mock import MockerFixture
    from respx import Router

URL = "https://compiler.test/api/compile"
LOCAL_URL = "http://127.0.0.1:8765/api/compile"
REQUEST = CompileRequest(
    filename=".gitedge/workflow/basic.yaml",
    source="source is never parsed by Python",
    event=CompileEvent(name="push", ref="refs/heads/main"),
)


@pytest.fixture(autouse=True)
def oidc_identity(mocker: MockerFixture) -> None:
    mocker.patch("app.clients.workflow_compiler.get_vercel_oidc_token", return_value="backend-identity")


async def test_compiler_http_contract_uses_auth_and_checks_version(httpx2_mock: Router) -> None:
    route = httpx2_mock.post(URL, headers={"x-vercel-trusted-oidc-idp-token": "backend-identity"}).respond(
        json=compiled_fixture().model_dump(mode="json", by_alias=True, exclude_none=True)
    )
    result = await HttpWorkflowCompiler(URL).compile(REQUEST)
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
        await HttpWorkflowCompiler(URL).compile(REQUEST)


async def test_compiler_response_size_and_missing_configuration_are_bounded(httpx2_mock: Router) -> None:
    with pytest.raises(CompilerUnavailableError, match="must be configured"):
        await HttpWorkflowCompiler(None).compile(REQUEST)
    httpx2_mock.post(URL).respond(content=b"x" * (MAX_COMPILER_RESPONSE + 1))
    with pytest.raises(CompilerUnavailableError, match="4 MiB"):
        await HttpWorkflowCompiler(URL).compile(REQUEST)


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
        await HttpWorkflowCompiler(URL).compile(request)
    assert not httpx2_mock.calls


async def test_oidc_identity_is_refreshed_for_each_request(httpx2_mock: Router, mocker: MockerFixture) -> None:
    identity = mocker.patch("app.clients.workflow_compiler.get_vercel_oidc_token", side_effect=["first", "second"])
    route = httpx2_mock.post(URL).respond(json=compiled_fixture().model_dump(mode="json", by_alias=True))
    compiler = HttpWorkflowCompiler(URL)
    await compiler.compile(REQUEST)
    await compiler.compile(REQUEST)
    assert [call.request.headers["x-vercel-trusted-oidc-idp-token"] for call in route.calls] == ["first", "second"]
    assert identity.await_count == 2


@pytest.mark.parametrize("token_error", [None, VercelOidcTokenError("No identity")])
async def test_missing_oidc_identity_fails_before_http(
    httpx2_mock: Router, mocker: MockerFixture, token_error: VercelOidcTokenError | None
) -> None:
    mocker.patch("app.clients.workflow_compiler.get_vercel_oidc_token", return_value="", side_effect=token_error)
    with pytest.raises(CompilerUnavailableError, match="OIDC identity"):
        await HttpWorkflowCompiler(URL).compile(REQUEST)
    assert not httpx2_mock.calls


async def test_local_development_compiler_needs_no_cloud_identity(httpx2_mock: Router, mocker: MockerFixture) -> None:
    mocker.patch.object(settings, "VERCEL_ENV", "development")
    identity = mocker.patch("app.clients.workflow_compiler.get_vercel_oidc_token")
    route = httpx2_mock.post(LOCAL_URL).respond(json=compiled_fixture().model_dump(mode="json", by_alias=True))
    assert await HttpWorkflowCompiler(LOCAL_URL).compile(REQUEST) == compiled_fixture()
    assert "x-vercel-trusted-oidc-idp-token" not in route.calls.last.request.headers
    identity.assert_not_awaited()


@pytest.mark.parametrize(
    ("environment", "url"),
    [("production", LOCAL_URL), ("preview", LOCAL_URL), ("development", "http://remote.test/api/compile")],
)
async def test_plaintext_compiler_is_restricted_to_local_development(
    httpx2_mock: Router, mocker: MockerFixture, environment: str, url: str
) -> None:
    mocker.patch.object(settings, "VERCEL_ENV", environment)
    with pytest.raises(CompilerUnavailableError, match="HTTPS"):
        await HttpWorkflowCompiler(url).compile(REQUEST)
    assert not httpx2_mock.calls
