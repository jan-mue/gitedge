from __future__ import annotations

import asyncio
import inspect
import uuid
from collections.abc import AsyncGenerator  # noqa: TC003 - injector inspects this test's provider annotations
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.workspaces import WorkspaceRef
from uncalled_for import Depends, FailedDependency, resolved_dependencies, without_dependencies
from vercel.sandbox import SandboxClient

from app.agents.dependencies import (
    AgentDeps,
    AgentDepsDep,
    AgentForgeScope,
    CodingAgentDeps,
    SetupAgentDeps,
    get_account_model,
    get_agent_deps,
    get_sandbox,
    inject,
)
from app.agents.main import run, run_agent_turn
from app.sandboxes.vercel import VercelSandbox
from app.schemas.agent_turns import AgentTurnRequest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from tests.unit.utils.fakes import FakeStores


def test_provider_capabilities_use_injected_clients(mocker: MockerFixture) -> None:
    vercel = mocker.create_autospec(SandboxClient, instance=True)
    capability = get_sandbox(vercel)
    assert isinstance(capability, VercelSandbox)
    assert capability.client is vercel


async def test_explicit_deps_bypass_production_graph(mocker: MockerFixture, fake_stores: FakeStores) -> None:
    deps = AgentDeps(streams=mocker.Mock(), blobs=fake_stores.blob)

    @without_dependencies
    async def execute(injected: AgentDepsDep) -> AgentDeps:
        return injected

    assert await execute(injected=deps) is deps


async def test_chained_dependencies_cache_resources_and_close_on_call_loop(mocker: MockerFixture) -> None:
    lifecycle: list[tuple[str, int]] = []
    vercel = mocker.create_autospec(SandboxClient, instance=True)

    @asynccontextmanager
    async def client() -> AsyncGenerator[SandboxClient]:
        lifecycle.append(("open", id(asyncio.get_running_loop())))
        try:
            yield vercel
        finally:
            await vercel.aclose()
            lifecycle.append(("close", id(asyncio.get_running_loop())))

    async def dependencies(
        first: object = Depends(get_sandbox, vercel=Depends(client)),
        second: object = Depends(get_sandbox, vercel=Depends(client)),
    ) -> None:
        del first, second

    async with resolved_dependencies(dependencies) as values:
        assert isinstance(values["first"], VercelSandbox)
        assert values["first"] is values["second"]
        assert values["first"].client is vercel
        assert len(lifecycle) == 1
    assert lifecycle[0][1] == lifecycle[1][1]
    assert [event[0] for event in lifecycle] == ["open", "close"]
    vercel.aclose.assert_awaited_once()


def test_forge_composes_with_workspace_resources(mocker: MockerFixture, fake_stores: FakeStores) -> None:
    streams = mocker.Mock()
    sandbox = mocker.Mock()
    common = get_agent_deps(streams, fake_stores.blob)
    forge = mocker.Mock()
    scope = AgentForgeScope(user_id=uuid.uuid4(), session_id=uuid.uuid4(), repository_ids=(uuid.uuid4(),))
    deps = CodingAgentDeps(streams=common.streams, blobs=common.blobs, sandbox=sandbox, forge=forge, forge_scope=scope)
    assert deps.streams is streams
    assert deps.blobs is fake_stores.blob
    assert deps.sandbox is sandbox
    assert deps.forge is forge
    assert deps.forge_scope is scope
    assert isinstance(deps, AgentDeps)


@pytest.mark.parametrize("handler", ["session", "turn"])
async def test_dependency_failure_is_raised_for_restate_retry(handler: str, mocker: MockerFixture) -> None:
    error = ConnectionError("dependency unavailable")
    failed = FailedDependency("resources", error)
    if handler == "session":
        call = run(
            mocker.Mock(),
            "run",
            resources=failed,  # ty: ignore[invalid-argument-type] - exercise failed injection
        )
    else:
        call = run_agent_turn(
            mocker.Mock(),
            mocker.Mock(),
            deps=failed,  # ty: ignore[invalid-argument-type] - exercise failed injection
            model=mocker.Mock(),
        )
    with pytest.raises(ConnectionError, match="dependency unavailable"):
        await call


@pytest.mark.parametrize("coding", [True, False])
async def test_execution_passes_explicit_deps_and_trusted_forge_scope(
    mocker: MockerFixture, fake_stores: FakeStores, *, coding: bool
) -> None:
    request = AgentTurnRequest(
        run_id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4()),
        user_id=uuid.uuid4(),
        prompt="Inspect the repository",
        model="ollama:real-model",
        instructions="Project conventions",
        workspace=WorkspaceRef(provider="smol", id="workspace"),
        repository_ids=[uuid.uuid4()],
        coding=coding,
    )
    common = AgentDeps(streams=mocker.Mock(), blobs=fake_stores.blob)
    forge = mocker.Mock()
    if coding:
        deps = CodingAgentDeps(
            streams=common.streams,
            blobs=common.blobs,
            sandbox=mocker.Mock(),
            forge=forge,
            forge_scope=AgentForgeScope(
                user_id=request.user_id,
                session_id=uuid.UUID(request.session_id),
                repository_ids=tuple(request.repository_ids),
            ),
        )
    else:
        deps = SetupAgentDeps(streams=common.streams, blobs=common.blobs, sandbox=mocker.Mock())
    workspace = mocker.Mock()
    mocker.patch("app.agents.main.workspace_backend", return_value=workspace)
    runner = "run_coding_agent" if coding else "run_setup_agent"
    run_agent = mocker.patch(f"app.agents.main.{runner}", return_value=[])
    model = TestModel()
    assert await run_agent_turn(mocker.Mock(), request, deps=deps, model=model) == []
    assert run_agent.await_args is not None
    injected = run_agent.await_args.args[0]
    assert run_agent.await_args.kwargs["workspace"] is workspace
    assert injected.streams is deps.streams
    assert run_agent.await_args.kwargs["model"] is model
    if coding:
        assert isinstance(injected, CodingAgentDeps)
        assert injected.forge is forge
        assert injected.forge_scope.user_id == request.user_id
        assert injected.forge_scope.session_id == uuid.UUID(request.session_id)
        assert injected.forge_scope.repository_ids == tuple(request.repository_ids)
    else:
        assert injected is deps


@pytest.mark.parametrize("failure", [False, True])
async def test_model_dependency_closes_model_before_credential_scope(mocker: MockerFixture, *, failure: bool) -> None:
    request = mocker.Mock(model="ollama:real-model", user_id=uuid.uuid4(), session_id=str(uuid.uuid4()))
    model = mocker.MagicMock()
    credentials = mocker.MagicMock()
    credentials.__aenter__.return_value = model
    account = mocker.patch("app.agents.dependencies.account_model", return_value=credentials)

    async def execute() -> None:
        async with get_account_model(request, mocker.Mock()) as resolved:
            assert resolved is model
            model.__aexit__.assert_not_awaited()
            credentials.__aexit__.assert_not_awaited()
            if failure:
                raise ValueError("execution interrupted")

    if failure:
        with pytest.raises(ValueError, match="execution interrupted"):
            await execute()
    else:
        await execute()
    model.__aexit__.assert_awaited_once()
    credentials.__aexit__.assert_awaited_once()
    assert account.call_args.kwargs["session_id"] == request.session_id


async def test_inject_preserves_typed_public_signature_and_positional_calls() -> None:
    resource = object()

    def provide_resource() -> object:
        return resource

    @inject
    async def handler(ctx: object, request: str, dependency: object = Depends(provide_resource)) -> str:
        assert ctx is not None
        assert dependency is resource
        return request

    signature = inspect.signature(handler)
    assert list(signature.parameters) == ["ctx", "request"]
    assert signature.parameters["request"].annotation is str
    assert signature.return_annotation is str
    assert await handler(object(), "positional") == "positional"
    assert await handler(ctx=object(), request="keyword") == "keyword"


async def test_explicit_dependency_keywords_bypass_resolution() -> None:
    def unavailable() -> object:
        raise AssertionError("An explicit dependency must bypass its provider")

    @inject
    async def handler(ctx: object, request: str, dependency: object = Depends(unavailable)) -> object:
        del ctx, request
        return dependency

    resource = object()
    assert await handler(object(), "override", dependency=resource) is resource


@pytest.mark.parametrize("failure", [False, True])
async def test_nested_dependency_lifetime_caching_and_failure_cleanup(*, failure: bool) -> None:
    lifecycle: list[str] = []
    resource = object()

    @asynccontextmanager
    async def provide_resource() -> AsyncGenerator[object]:
        lifecycle.append("open")
        try:
            yield resource
        finally:
            lifecycle.append("close")

    def provide_nested(value: object = Depends(provide_resource)) -> object:
        return value

    @inject
    async def handler(
        ctx: object,
        request: str,
        first: object = Depends(provide_nested),
        second: object = Depends(provide_nested),
    ) -> str:
        del ctx
        assert first is second is resource
        assert lifecycle == ["open"]
        if failure:
            raise ValueError("interrupted")
        return request

    if failure:
        with pytest.raises(ValueError, match="interrupted"):
            await handler(object(), "failure")
    else:
        assert await handler(object(), "success") == "success"
    assert lifecycle == ["open", "close"]


async def test_handler_without_dependencies_retains_normal_defaults() -> None:
    @inject
    async def handler(ctx: object, request: str = "default") -> str:
        del ctx
        return request

    assert await handler(object()) == "default"
    assert inspect.signature(handler).return_annotation is str
