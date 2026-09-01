"""API router aggregation for the application."""

from fastapi import APIRouter

from app.api.routes import git, login, private, repositories, users, utils
from app.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(git.router)
api_router.include_router(repositories.router)
api_router.include_router(utils.router)


if settings.VERCEL_ENV == "development":
    api_router.include_router(private.router)
