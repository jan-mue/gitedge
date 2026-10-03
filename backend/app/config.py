"""Application configuration settings."""

import json
import logging
import secrets
import warnings
from enum import StrEnum
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import (
    EmailStr,
    HttpUrl,
    PostgresDsn,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Origin(s) allowed for local development (Vite dev server).
DEV_FRONTEND_ORIGINS: tuple[str, ...] = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def _normalize_origin(value: str) -> str | None:
    value = value.strip()
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    if parsed.path or parsed.query or parsed.fragment:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _preview_hosts(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Ignoring malformed VERCEL_RELATED_PROJECTS")
        return []
    if not isinstance(payload, list):
        return []
    hosts: list[str] = []
    for entry in payload:
        preview = entry.get("preview") if isinstance(entry, dict) else None
        if not isinstance(preview, dict):
            continue
        for field in ("customEnvironment", "branch"):
            value = preview.get(field)
            if isinstance(value, str) and value:
                hosts.append(value)
    return hosts


class LogLevel(StrEnum):
    """Log level options for the application."""

    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    # Allow public self-service sign-ups via POST /users/signup.
    SIGNUPS_ENABLED: bool = True
    FRONTEND_HOST: str = "http://localhost:5173"
    VERCEL_ENV: Literal["development", "preview", "production"] = "development"
    # Set by Vercel when `relatedProjects` is declared in vercel.json.
    VERCEL_RELATED_PROJECTS: str | None = None

    LOG_LEVEL: LogLevel = LogLevel.INFO

    PROJECT_NAME: str
    SENTRY_DSN: HttpUrl | None = None
    DATABASE_URL: PostgresDsn

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _use_psycopg_driver(cls, value: str | PostgresDsn) -> str:
        database_url = str(value)
        for scheme in ("postgres://", "postgresql://"):
            if database_url.startswith(scheme):
                return database_url.replace(scheme, "postgresql+psycopg://", 1)
        return database_url

    # Redis settings
    REDIS_KIND: Literal["redis", "rest"] = "redis"
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: str | None = None

    # Blob storage settings
    BLOB_STORAGE_KIND: Literal["vercel", "s3"] = "s3"
    VERCEL_BLOB_TOKEN: str | None = None
    # Access mode of the Vercel Blob store. Must match the store's configuration.
    VERCEL_BLOB_ACCESS: Literal["public", "private"] = "private"
    S3_ENDPOINT: str | None = "127.0.0.1:9000"
    S3_ACCESS_KEY: str | None = "minioadmin"
    S3_SECRET_KEY: str | None = "minioadmin"  # noqa: S105
    S3_BUCKET: str | None = "gitedge"
    S3_SECURE: bool = False

    # Email settings
    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: str | None = None

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        """Check if email sending is properly configured."""
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", for security, please change it, at least for deployments.'
            )
            if self.VERCEL_ENV == "development":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        for host in self.DATABASE_URL.hosts():
            self._check_default_secret("DATABASE_URL password", host["password"])
        self._check_default_secret("FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD)

        return self

    @property
    def cors_origins(self) -> list[str]:
        """Allowed CORS origins for the current environment."""
        if self.VERCEL_ENV == "production":
            candidates = [self.FRONTEND_HOST]
        elif self.VERCEL_ENV == "preview":
            candidates = _preview_hosts(self.VERCEL_RELATED_PROJECTS)
        else:
            candidates = list(DEV_FRONTEND_ORIGINS)

        origins: list[str] = []
        for candidate in candidates:
            normalized = _normalize_origin(candidate)
            if normalized is not None and normalized not in origins:
                origins.append(normalized)
        return origins


settings = Settings()
