"""API router aggregation for the application."""

from fastapi import APIRouter

from app.api.routes import (
    activity,
    comments,
    forks,
    git,
    login,
    private,
    profiles,
    releases,
    repositories,
    stars,
    users,
    utils,
    watchers,
)
from app.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(git.router)
api_router.include_router(stars.router)
api_router.include_router(stars.user_router)
api_router.include_router(watchers.router)
api_router.include_router(forks.router)
api_router.include_router(comments.router)
api_router.include_router(releases.router)
api_router.include_router(activity.router)
api_router.include_router(activity.user_router)
api_router.include_router(profiles.router)
api_router.include_router(repositories.router)
api_router.include_router(utils.router)


if settings.VERCEL_ENV == "development":
    api_router.include_router(private.router)
