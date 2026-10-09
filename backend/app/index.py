"""FastAPI application setup and configuration."""

import logging
from typing import TYPE_CHECKING

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.main import api_router
from app.api.routes import git
from app.config import settings
from app.exceptions import NotFoundError
from app.lifespan import lifespan
from app.utils.setup_logging import setup_logging

if TYPE_CHECKING:
    from fastapi.routing import APIRoute

logger = logging.getLogger(__name__)

setup_logging(level=logging.DEBUG if settings.VERCEL_ENV == "development" else logging.INFO, logger_name="app")


def custom_generate_unique_id(route: APIRoute) -> str:
    """Generate a unique operation ID for each route based on tag and name."""
    if route.tags:
        return f"{route.tags[0]}-{route.name}"
    return route.name


if settings.SENTRY_DSN and settings.VERCEL_ENV != "development":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions, logging them with a stack trace."""
    logger.error("Unhandled exception - %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.exception_handler(NotFoundError)
async def not_found_exception_handler(_request: Request, exc: NotFoundError) -> JSONResponse:
    """Handle not-found errors raised by the store layer."""
    return JSONResponse(status_code=404, content={"detail": exc.detail})


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

# Mount git router at root level for git client access (e.g., /<owner>/<repo>.git/info/refs)
# This allows git clients to use clean URLs without the /api/v1/ prefix.
# Excluded from OpenAPI docs to avoid duplicate operation IDs with /api/v1/ routes.
app.include_router(git.router, include_in_schema=False)
