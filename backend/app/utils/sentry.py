"""Sentry error monitoring configuration."""

import logging

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.config import settings


def init_sentry() -> None:
    """Initialize Sentry when a DSN is configured."""
    if not settings.SENTRY_DSN:
        return

    sentry_sdk.init(
        dsn=str(settings.SENTRY_DSN),
        enable_logs=True,
        traces_sample_rate=settings.SENTRY_SAMPLE_RATE,
        environment=settings.VERCEL_ENV,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            LoggingIntegration(
                level=logging.getLevelNamesMapping()[settings.LOG_LEVEL.value],
                event_level=logging.ERROR,
            ),
            SqlalchemyIntegration(),
            RedisIntegration(),
        ],
    )
