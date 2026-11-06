"""Translate expected application failures at the HTTP boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse

from app.exceptions import (
    ApplicationError,
    AuthenticationError,
    ConflictError,
    InvalidInputError,
    NotFoundError,
    PayloadTooLargeError,
    PermissionDeniedError,
    RateLimitError,
    ServiceUnavailableError,
    UnprocessableInputError,
)

if TYPE_CHECKING:
    from fastapi import Request

ERROR_STATUS: dict[type, int] = {
    ApplicationError: 500,
    InvalidInputError: 400,
    AuthenticationError: 401,
    PermissionDeniedError: 403,
    NotFoundError: 404,
    ConflictError: 409,
    PayloadTooLargeError: 413,
    UnprocessableInputError: 422,
    RateLimitError: 429,
    ServiceUnavailableError: 503,
}


async def application_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Preserve public error details and protocol headers for domain failures."""
    if not isinstance(exc, ApplicationError):
        raise TypeError("Expected an application error")
    status_code = next(ERROR_STATUS[base] for base in type(exc).__mro__ if base in ERROR_STATUS)
    headers = {}
    if isinstance(exc, AuthenticationError):
        headers["WWW-Authenticate"] = exc.challenge
    if isinstance(exc, RateLimitError):
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse(status_code=status_code, content={"detail": exc.detail}, headers=headers)
