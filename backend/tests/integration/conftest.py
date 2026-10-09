from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import random
import shutil
import socket
import string
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import psycopg
import pytest
import redis
from alembic.command import upgrade
from alembic.config import Config
from playwright.sync_api import expect
from pydantic import PostgresDsn, TypeAdapter
from testcontainers.mailpit import MailpitContainer
from testcontainers.minio import MinioContainer
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer
from xprocess import ProcessStarter

from app.clients.blob_storage import S3Client
from app.config import settings
from app.constants import BACKEND_DIR
from app.utils.security import get_password_hash

if TYPE_CHECKING:
    from collections.abc import Coroutine, Generator

    from playwright.sync_api import Page
    from xprocess import XProcess


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, Any]) -> dict[str, Any]:
    """Configure browser context with desktop viewport.

    The sidebar is hidden on mobile viewports (< 768px width), so we need
    to ensure tests run with a desktop viewport to see the user-menu.

    Args:
        browser_context_args: Default browser context arguments.

    Returns:
        Updated browser context arguments with desktop viewport.
    """
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
    }


FIRST_SUPERUSER = os.environ.get("FIRST_SUPERUSER", "admin@example.com")
FIRST_SUPERUSER_PASSWORD = os.environ.get("FIRST_SUPERUSER_PASSWORD", "changethis_admin_password_secure")


@pytest.fixture(scope="session")
def mailpit_container() -> Generator[MailpitContainer]:
    """Start a Mailpit container for email testing."""
    with MailpitContainer() as container:
        yield container


@pytest.fixture(scope="session")
def mailpit_http_url(mailpit_container: MailpitContainer) -> str:
    """Get the Mailpit HTTP API URL."""
    return mailpit_container.get_base_api_url()


@pytest.fixture(scope="session")
def mailpit_smtp_host(mailpit_container: MailpitContainer) -> str:
    """Get the Mailpit SMTP host."""
    return mailpit_container.get_container_host_ip()


@pytest.fixture(scope="session")
def mailpit_smtp_port(mailpit_container: MailpitContainer) -> int:
    """Get the Mailpit SMTP port."""
    return mailpit_container.get_exposed_smtp_port()


@pytest.fixture(scope="session")
def infrastructure(mailpit_smtp_host: str, mailpit_smtp_port: int) -> Generator[dict[str, str]]:
    """Start infrastructure containers (DB, Redis, MinIO)."""
    with (
        PostgresContainer("postgres:18.2", driver="psycopg") as postgres,
        RedisContainer("redis:8.6.0") as redis,
        MinioContainer(
            "cgr.dev/chainguard/minio@sha256:9dcc028b309030afa86fc1fc8d93907ae373ea3fb75277cca3fc77e4645932b7"
        ) as minio,
    ):
        db_url = postgres.get_connection_url()
        redis_url = f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0"

        minio_endpoint = f"{minio.get_container_host_ip()}:{minio.get_exposed_port(9000)}"

        env = {
            "DATABASE_URL": db_url,
            "REDIS_URL": redis_url,
            "BLOB_STORAGE_KIND": "s3",
            "S3_ENDPOINT": minio_endpoint,
            "S3_ACCESS_KEY": minio.access_key,
            "S3_SECRET_KEY": minio.secret_key,
            "S3_BUCKET": "gitedge-test",
            "S3_SECURE": "False",
            "SMTP_HOST": mailpit_smtp_host,
            "SMTP_PORT": str(mailpit_smtp_port),
            "SMTP_TLS": "False",
            "EMAILS_FROM_EMAIL": "noreply@example.com",
            # We want settings to pick these up, but subprocesses definitely need them in os.environ
            "NODE_ENV": "test",
        }

        config = Config(BACKEND_DIR / "alembic.ini")
        config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
        # Migrate the ephemeral Postgres test container via settings.DATABASE_URL.
        settings.DATABASE_URL = TypeAdapter(PostgresDsn).validate_python(db_url)
        os.environ["DATABASE_URL"] = db_url
        upgrade(config, "head")

        user_id = str(uuid.uuid4())
        hashed_password = get_password_hash(FIRST_SUPERUSER_PASSWORD)
        username = FIRST_SUPERUSER.split("@")[0]

        with psycopg.connect(db_url.replace("postgresql+psycopg://", "postgresql://")) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO principal (id, name, lower_name, display_name, type)
                    VALUES (%s, %s, %s, 'Admin User', 'user')
                    ON CONFLICT (lower_name) DO NOTHING
                """,
                    (user_id, username, username.lower()),
                )
                cur.execute(
                    """
                    INSERT INTO "user" (id, email, is_active, is_superuser, hashed_password)
                    VALUES (%s, %s, True, True, %s)
                    ON CONFLICT (email) DO NOTHING
                """,
                    (user_id, "admin@example.com", hashed_password),
                )
            conn.commit()

        yield env


def _delete_repository_rows() -> None:
    """Delete all repository-related rows from the database."""
    db_url = str(settings.DATABASE_URL).replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(db_url) as conn:
        conn.execute("DELETE FROM activity")
        conn.execute("DELETE FROM comment")
        conn.execute("DELETE FROM star")
        conn.execute("DELETE FROM watcher")
        conn.execute("DELETE FROM release")
        conn.execute("DELETE FROM pull_request")
        conn.execute("DELETE FROM issue")
        conn.execute("DELETE FROM repository")


def create_repository_row(owner: str, name: str) -> None:
    """Insert a repository row for an owner without any stored Git data.

    Args:
        owner: Owner (user or organization) name.
        name: Repository name.
    """
    db_url = str(settings.DATABASE_URL).replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(db_url) as conn:
        conn.execute(
            """
            INSERT INTO repository (id, owner_id, name, is_private, default_branch)
            SELECT %s, id, %s, false, 'main' FROM principal WHERE lower_name = %s
            """,
            (str(uuid.uuid4()), name, owner.lower()),
        )


def _delete_redis_keys(redis_url: str) -> None:
    """Delete all keys from Redis.

    Args:
        redis_url: Redis connection URL.
    """
    client = redis.Redis.from_url(redis_url)
    try:
        for key in client.scan_iter("*"):
            client.delete(key)
    finally:
        client.close()


async def _delete_blob_objects(infrastructure: dict[str, str]) -> None:
    """Delete all objects from blob storage.

    Args:
        infrastructure: Infrastructure connection details.
    """
    client = S3Client(
        endpoint=infrastructure["S3_ENDPOINT"],
        access_key=infrastructure["S3_ACCESS_KEY"],
        secret_key=infrastructure["S3_SECRET_KEY"],
        bucket=infrastructure["S3_BUCKET"],
        secure=infrastructure["S3_SECURE"] == "True",
    )
    for key in await client.list_keys(""):
        await client.delete(key)


def _run_async(coroutine: Coroutine[Any, Any, None]) -> None:
    """Run a coroutine in a dedicated thread with its own event loop.

    Args:
        coroutine: The coroutine to run.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(asyncio.run, coroutine).result()


def delete_all_repositories(infrastructure: dict[str, str]) -> None:
    """Delete all repositories from the database, Redis and blob storage.

    Args:
        infrastructure: Infrastructure connection details.
    """
    _delete_repository_rows()
    _delete_redis_keys(infrastructure["REDIS_URL"])
    _run_async(_delete_blob_objects(infrastructure))


@pytest.fixture(autouse=True)
def clean_repositories(infrastructure: dict[str, str]) -> Generator[None]:
    """Remove all repositories after each test.

    Args:
        infrastructure: Infrastructure connection details.

    Yields:
        None.
    """
    yield
    delete_all_repositories(infrastructure)


@pytest.fixture(scope="session")
def app_url(infrastructure: dict[str, str], xprocess: XProcess) -> Generator[str]:
    """Start Uvicorn and Vite servers, returning Vite's URL for full-stack tests."""

    # 1. Start Backend (Uvicorn)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        backend_port = s.getsockname()[1]

    backend_env = os.environ.copy()
    backend_env.update(infrastructure)
    backend_cwd = Path(__file__).resolve().parent.parent.parent

    class BackendStarter(ProcessStarter):  # type: ignore[misc]
        terminate_on_interrupt = True
        pattern = "Application startup complete"
        env = backend_env
        args = [sys.executable, "-m", "uvicorn", "app.index:app", "--port", str(backend_port)]
        popen_kwargs = {"cwd": backend_cwd}
        max_read_lines = 1000

    backend_base_url = f"http://127.0.0.1:{backend_port}"
    xprocess.ensure("backend", BackendStarter)

    # 2. Start Frontend (Vite)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        frontend_port = s.getsockname()[1]

    frontend_env = os.environ.copy()
    frontend_env["API_URL"] = backend_base_url
    frontend_cwd = backend_cwd.parent / "frontend"
    bun_path = shutil.which("bun") or "bun"

    class FrontendStarter(ProcessStarter):  # type: ignore[misc]
        terminate_on_interrupt = True
        pattern = "ready in"
        env = frontend_env
        args = [bun_path, "run", "dev", "--port", str(frontend_port)]
        popen_kwargs = {"cwd": frontend_cwd}
        max_read_lines = 1000

    frontend_base_url = f"http://localhost:{frontend_port}"
    xprocess.ensure("frontend", FrontendStarter)

    yield frontend_base_url

    xprocess.getinfo("frontend").terminate()
    xprocess.getinfo("backend").terminate()


@pytest.fixture
def random_email() -> str:
    """Generate a random email address for testing."""
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=7))
    return f"test_{suffix}@example.com"


@pytest.fixture
def random_password() -> str:
    """Generate a random password for testing."""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=12))


@dataclass
class UserCredentials:
    """Test user data container."""

    email: str
    password: str


@pytest.fixture
def test_user(app_url: str, random_email: str, random_password: str) -> UserCredentials:
    """Create a test user via the API and return credentials."""
    create_user_via_api(app_url, random_email, random_password)
    return UserCredentials(email=random_email, password=random_password)


@pytest.fixture
def logged_in_test_user(page: Page, app_url: str, test_user: UserCredentials) -> UserCredentials:
    """Create and log in a test user."""
    log_in_user(page, app_url, test_user.email, test_user.password)
    return test_user


@pytest.fixture
def logged_in_superuser(page: Page, app_url: str) -> None:
    """Log in as superuser before the test."""
    log_in_user(page, app_url, FIRST_SUPERUSER, FIRST_SUPERUSER_PASSWORD)


def create_user_via_api(api_base_url: str, email: str, password: str) -> dict[str, Any]:
    """Create a user via the private API."""
    data = json.dumps(
        {
            "email": email,
            "password": password,
            "is_verified": True,
            "display_name": "Test User",
        }
    ).encode("utf-8")

    # TODO: use httpx
    req = urllib.request.Request(
        f"{api_base_url}/api/v1/private/users/",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req) as response:
        result: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        return result


def log_in_user(page: Page, base_url: str, email: str, password: str) -> None:
    page.goto(f"{base_url}/login")
    page.get_by_test_id("email-input").fill(email)
    page.get_by_test_id("password-input").fill(password)
    page.get_by_role("button", name="Log In").click()
    page.wait_for_url(f"{base_url}/")
    expect(page.get_by_test_id("dashboard-feed")).to_be_visible()
    expect(page.get_by_test_id("user-menu")).to_be_visible(timeout=30000)


def log_out_user(page: Page, base_url: str) -> None:
    page.get_by_test_id("user-menu").click()
    page.get_by_role("menuitem", name="Sign Out").click()
    page.goto(f"{base_url}/login")


def sign_up_new_user(page: Page, base_url: str, name: str, email: str, password: str) -> None:
    page.goto(f"{base_url}/signup")
    page.get_by_test_id("full-name-input").fill(name)
    page.get_by_test_id("email-input").fill(email)
    page.get_by_test_id("password-input").fill(password)
    page.get_by_test_id("confirm-password-input").fill(password)
    page.get_by_role("button", name="Sign Up").click()
    page.goto(f"{base_url}/login")


def find_last_email(mailpit_http_url: str, recipient_filter: str | None = None, timeout: int = 5000) -> dict[str, Any]:
    start_time = time.time()
    timeout_seconds = timeout / 1000

    while time.time() - start_time < timeout_seconds:
        try:
            req = urllib.request.Request(f"{mailpit_http_url}/api/v1/messages")
            with urllib.request.urlopen(req, timeout=1) as response:
                data = json.loads(response.read().decode("utf-8"))
                messages = data.get("messages", [])

            if recipient_filter:
                filtered = []
                for msg in messages:
                    recipients = msg.get("To", [])
                    for recipient in recipients:
                        if recipient_filter in recipient.get("Address", ""):
                            filtered.append(msg)
                            break
                messages = filtered

            if messages:
                result: dict[str, Any] = messages[0]
                return result
        except urllib.error.URLError, OSError:
            pass

        time.sleep(0.1)

    raise RuntimeError("Timeout while trying to get latest email")


def get_email_html(mailpit_http_url: str, message_id: str) -> str:
    req = urllib.request.Request(f"{mailpit_http_url}/api/v1/message/{message_id}")
    with urllib.request.urlopen(req, timeout=5) as response:
        data = json.loads(response.read().decode("utf-8"))
        html: str = data.get("HTML", "")
        return html
