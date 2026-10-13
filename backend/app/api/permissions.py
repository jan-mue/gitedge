"""Permission decorators operating on explicitly declared route arguments."""

from __future__ import annotations

from functools import wraps
from inspect import signature
from typing import TYPE_CHECKING, cast, get_type_hints

from fastapi import HTTPException, Request, Response, status

from app.entities.users import User
from app.services.authorization import AuthorizationService

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


def require_permission[**P, R](
    permission: str | Callable[[Request], str],
    *,
    authorization: str = "authorization",
    user: str = "current_user",
    response: str = "response",
    challenge: str = "Bearer",
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Check permissions using the handler's owner, repo, authorization, and current_user.

    All four arguments must appear in the original handler signature. The decorator
    adds no parameters and injects no repository object. FastAPI still wires the
    authentication and service arguments explicitly declared by that handler.
    """

    def decorate(handler: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        # Resolve annotations in the handler's namespace before functools.wraps
        # copies them; postponed annotations otherwise resolve in this module.
        handler.__annotations__ = get_type_hints(handler, include_extras=True)
        if handler.__annotations__.get("return") is type(None):
            handler.__annotations__["return"] = None
        route_signature = signature(handler)
        route_name = getattr(handler, "__name__", type(handler).__name__)
        required = {"owner", "repo", authorization, user}
        if not required.issubset(route_signature.parameters):
            raise TypeError(f"{route_name} must explicitly declare {', '.join(sorted(required))}")
        if not isinstance(permission, str) and "request" not in route_signature.parameters:
            raise TypeError(f"{route_name} must declare request for a dynamic permission")

        @wraps(handler)
        async def authorized(*args: P.args, **kwargs: P.kwargs) -> R:
            bound = route_signature.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = bound.arguments
            service = cast(AuthorizationService, arguments[authorization])
            current_user = cast(User | None, arguments[user])
            repository = await service.repositories.get_by_owner_and_name(
                cast(str, arguments["owner"]), cast(str, arguments["repo"])
            )
            action = permission if isinstance(permission, str) else permission(cast(Request, arguments["request"]))
            try:
                await service.require(repository, current_user, action)
            except HTTPException as error:
                if error.status_code == status.HTTP_401_UNAUTHORIZED:
                    error.headers = {"WWW-Authenticate": challenge}
                raise
            result = await handler(*args, **kwargs)
            http_response = arguments.get(response)
            if isinstance(http_response, Response) and (
                repository.is_private or (current_user is not None and "Cache-Control" not in http_response.headers)
            ):
                http_response.headers["Cache-Control"] = "private, no-store"
            if repository.is_private and isinstance(result, Response):
                result.headers["Cache-Control"] = "private, no-store"
            return result

        return authorized

    return decorate
