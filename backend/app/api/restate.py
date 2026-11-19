"""Request-scoped FastAPI dependencies for the native mounted Restate app."""

from contextlib import AsyncExitStack
from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.dependencies.utils import get_dependant, solve_dependencies
from fastapi.exceptions import RequestValidationError

from app.agents.dependencies import CODING_AGENT_DEPS, CodingAgentDeps
from app.api.dependencies import CodingAgentDepsDep  # noqa: TC001 - FastAPI resolves dependency annotations at mount time

if TYPE_CHECKING:
    from fastapi import FastAPI
    from starlette.types import ASGIApp, Receive, Scope, Send


async def bind_dependencies(deps: CodingAgentDepsDep) -> CodingAgentDeps:
    """Describe the dependency graph without creating a protocol path operation."""
    return deps


class RestateDependencies:
    """Resolve the existing FastAPI graph without intercepting the SDK's ASGI stream."""

    def __init__(self, app: ASGIApp, *, dependency_overrides_provider: FastAPI) -> None:
        """Use the parent app's dependency overrides and request-lifetime resources."""
        self.app = app
        self.provider = dependency_overrides_provider
        self.dependency = get_dependant(path="/restate", call=bind_dependencies)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Keep dependency resources alive until the mounted SDK app finishes."""
        if scope["type"] != "http" or not scope["path"].startswith("/restate/"):
            await self.app(scope, receive, send)
            return
        async with AsyncExitStack() as request_stack, AsyncExitStack() as function_stack:
            dependency_scope = {
                **scope,
                "fastapi_inner_astack": request_stack,
                "fastapi_function_astack": function_stack,
            }
            solved = await solve_dependencies(
                request=Request(dependency_scope, receive=receive),
                dependant=self.dependency,  # codespell:ignore dependant
                dependency_overrides_provider=self.provider,
                async_exit_stack=request_stack,
                embed_body_fields=False,
            )
            if solved.errors:
                raise RequestValidationError(solved.errors)
            deps = solved.values["deps"]
            if not isinstance(deps, CodingAgentDeps):
                raise TypeError("Restate dependency graph did not return CodingAgentDeps")
            token = CODING_AGENT_DEPS.set(deps)
            try:
                await self.app(scope, receive, send)
            finally:
                CODING_AGENT_DEPS.reset(token)
