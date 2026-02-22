import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from loguru import logger

from app.api.main import api_router
from app.config import settings
from app.utils.configure_logging import configure_logging


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


configure_logging()

if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions and log them with Loguru."""
    logger.exception(f"Unhandled exception: {exc} - Path: {request.url.path}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_methods=["*"],
        allow_credentials=True,
        allow_headers=["authorization", "X-Requested-With", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)
