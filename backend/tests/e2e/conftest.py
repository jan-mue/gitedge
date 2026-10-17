from __future__ import annotations

import json
import os
import shutil
import socket
import time
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any

import pytest
from playwright.sync_api import expect
from xprocess import ProcessStarter

from app.constants import BACKEND_DIR
from tests.conftest import FIRST_SUPERUSER, FIRST_SUPERUSER_PASSWORD, UserCredentials

if TYPE_CHECKING:
    from collections.abc import Generator

    from playwright.sync_api import Page
    from xprocess import XProcess


@pytest.fixture(autouse=True)
def _clean_repositories(clean_repositories: None) -> None:
    pass


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict[str, Any]) -> dict[str, Any]:
    """Allow local verification with a system Chromium installation."""
    executable = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
    return {**browser_type_launch_args, **({"executable_path": executable} if executable else {})}


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


@pytest.fixture(scope="session")
def app_url(backend_url: str, xprocess: XProcess) -> Generator[str]:
    """Start Vite against the shared backend for browser tests."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        frontend_port = s.getsockname()[1]

    frontend_env = os.environ.copy()
    frontend_env["API_URL"] = backend_url
    frontend_cwd = BACKEND_DIR.parent / "frontend"
    bun_path = shutil.which("bun") or "bun"

    class FrontendStarter(ProcessStarter):  # type: ignore[misc]
        terminate_on_interrupt = True
        pattern = "ready in"
        env = frontend_env
        args = [bun_path, "run", "dev", "--port", str(frontend_port)]
        popen_kwargs = {"cwd": frontend_cwd}
        max_read_lines = 1000

    frontend_base_url = f"http://localhost:{frontend_port}"
    xprocess.ensure("frontend", FrontendStarter, restart=True)

    yield frontend_base_url

    xprocess.getinfo("frontend").terminate()


@pytest.fixture
def logged_in_test_user(page: Page, app_url: str, test_user: UserCredentials) -> UserCredentials:
    """Create and log in a test user."""
    log_in_user(page, app_url, test_user.email, test_user.password)
    return test_user


@pytest.fixture
def logged_in_superuser(page: Page, app_url: str) -> None:
    """Log in as superuser before the test."""
    log_in_user(page, app_url, FIRST_SUPERUSER, FIRST_SUPERUSER_PASSWORD)


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
