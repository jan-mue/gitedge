"""Browser-to-API-to-sandbox workflow execution."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2 as httpx
import pytest
from playwright.sync_api import expect

from tests.conftest import FIRST_SUPERUSER, FIRST_SUPERUSER_PASSWORD
from tests.git import run_git

if TYPE_CHECKING:
    from pathlib import Path

    from playwright.sync_api import Page


@pytest.mark.usefixtures("logged_in_superuser")
def test_actions_dispatch_checkout_and_live_logs(page: Page, app_url: str, backend_url: str, tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    run_git(source, ["init", "-b", "main"])
    run_git(source, ["config", "user.name", "CI Test"])
    run_git(source, ["config", "user.email", "ci@example.com"])
    (source / "README.md").write_text("# Browser Actions\n")
    workflow = source / ".gitedge/workflow/browser.yaml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("""name: Browser CI
on: workflow_dispatch
jobs:
  hello:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
      - name: Say hello
        run: |
          test -f README.md
          echo "Hello from the sandbox"
""")
    run_git(source, ["add", "."])
    run_git(source, ["commit", "-m", "Browser CI fixture"])
    run_git(source, ["remote", "add", "origin", f"{backend_url}/admin/browser-actions.git"])
    run_git(source, ["push", "origin", "main"])
    with httpx.Client(base_url=backend_url, timeout=180) as api:
        login = api.post(
            "/api/v1/login/access-token", data={"username": FIRST_SUPERUSER, "password": FIRST_SUPERUSER_PASSWORD}
        )
        login.raise_for_status()
        api.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        try:
            page.goto(f"{app_url}/admin/browser-actions/actions")
            page.get_by_role("button", name="browser.yaml", exact=True).click()
            page.get_by_role("button", name="Run workflow", exact=True).click()
            expect(page.get_by_role("heading", name="Browser CI", exact=True)).to_be_visible(timeout=180000)
            expect(page.get_by_role("img", name="success", exact=True).first).to_be_visible(timeout=180000)
            page.get_by_role("button", name="success Say hello").click()
            expect(page.get_by_text("Hello from the sandbox", exact=False).first).to_be_visible()
            assert "?run=" in page.url
            page.reload()
            expect(page.get_by_role("heading", name="Browser CI", exact=True)).to_be_visible()
            page.screenshot(path="/tmp/gitedge-actions-browser.png", full_page=True)
        finally:
            runs = api.get("/api/v1/repositories/admin/browser-actions/actions/runs")
            runs.raise_for_status()
            for run in runs.json():
                api.post(f"/api/v1/repositories/admin/browser-actions/actions/runs/{run['id']}/cancel")
