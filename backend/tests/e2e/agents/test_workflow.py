"""A CI-sized real agent workflow: tiny Git repository, saved chat, and a GitEdge PR."""

import json
import os
import re
import shlex
import shutil
import subprocess
import time
from typing import TYPE_CHECKING

import pytest
from dulwich.refs import Ref, check_ref_format
from playwright.sync_api import expect

from app.schemas.agents import RunPublic
from tests.git import push_repo

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from tests.e2e.agents.conftest import GitState, PublicationTools


SETUP_SCRIPT = """set -eu
cd -- "$(dirname -- "$0")/../.."
printf '%s\\n' 'No packages or builds are needed. If asked to edit files, only README.md may change.' > AGENTS.md
grep -qxF AGENTS.md .git/info/exclude || printf '%s\\n' AGENTS.md >> .git/info/exclude
printf 'AGENT_SETUP_READY\\n'
"""


def failure_details(run: RunPublic) -> str:
    """Return root and child journals before the shared SDK harness shuts down."""
    cli = shutil.which("restate")
    if cli is None or run.invocation_id is None:
        return f"status={run.status}, error={run.error}, invocation={run.invocation_id}; Restate CLI unavailable"
    env = {**os.environ, "RESTATE_AUTH_TOKEN": ""}
    children = subprocess.run(
        [cli, "invocations", "list", "--service", "GitEdgeAgentTurns", "--all", "--json"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    ids = [run.invocation_id]
    if children.returncode == 0:
        ids.extend(
            item["id"]
            for item in json.loads(children.stdout).get("invocations", [])
            if item.get("invoked_by_id") == run.invocation_id
        )
    output = []
    for invocation_id in ids:
        for arguments in (
            ["describe", invocation_id, "--json"],
            ["journal", invocation_id, "--all", "--payload", "--json"],
        ):
            result = subprocess.run(
                [cli, "invocations", *arguments], env=env, capture_output=True, text=True, check=False
            )
            output.append(result.stdout + result.stderr)
    return "\n".join(output)


def send(page: Page, prompt: str) -> RunPublic:
    """Submit through the actual composer and retain the accepted durable run."""
    expect(page.get_by_role("combobox", name="Model", exact=True)).not_to_have_value("")
    page.get_by_label("Message agent", exact=True).fill(prompt)
    with page.expect_response(
        lambda response: (
            "/agents/sessions/" in response.url and response.url.endswith("/runs") and response.request.method == "POST"
        )
    ) as accepted:
        page.get_by_role("button", name="Send message", exact=True).click()
    assert accepted.value.status == 202
    run = RunPublic.model_validate(accepted.value.json())
    page.wait_for_url(re.compile(rf"/agents\?session={run.session_id}$"))
    return run


def finish(page: Page, app_url: str, run: RunPublic) -> RunPublic:
    """Reload during real execution, then wait for authoritative terminal state and UI reattachment."""
    page.reload()
    headers = {"Authorization": f"Bearer {page.evaluate('localStorage.getItem("access_token")')}"}
    deadline = time.monotonic() + 300
    result = run
    while result.status in {"pending", "running"}:
        if time.monotonic() >= deadline:
            pytest.fail(f"Run {run.id} did not finish: {result.status}\n{failure_details(result)}")
        response = page.request.get(f"{app_url}/api/v1/agents/runs/{run.id}", headers=headers)
        assert response.status == 200
        result = RunPublic.model_validate(response.json())
        if result.status in {"pending", "running"}:
            page.wait_for_timeout(500)
    if result.status != "completed":
        pytest.fail(f"Run {run.id} ended with {result.status}: {result.error}\n{failure_details(result)}")
    assert result.finished_at is not None
    expect(page.get_by_label("Message agent", exact=True)).to_be_enabled(timeout=30000)
    return result


@pytest.mark.usefixtures("logged_in_superuser")
def test_tiny_agent_change_creates_a_gitedge_pull_request(
    page: Page, app_url: str, backend_url: str, publication_tools: PublicationTools, git_state: GitState
) -> None:
    """Use real models, native compute, Git storage, and the browser; never synthesize agent results."""
    api = f"{app_url}/api/v1"
    headers = {"Authorization": f"Bearer {page.evaluate('localStorage.getItem("access_token")')}"}
    me = page.request.get(f"{api}/users/me", headers=headers)
    assert me.status == 200
    owner = me.json()["name"]
    name = "tiny-agent-pr"
    repository = f"{owner}/{name}"
    push_repo(backend_url, f"{repository}.git")
    info = page.request.get(f"{api}/repositories/{repository}/info", headers=headers)
    assert info.status == 200
    base_commit = info.json()["last_commit"]["sha"]
    options = page.request.get(f"{api}/users/me/personal-access-tokens/repositories", headers=headers)
    assert options.status == 200
    repository_id = next(item["id"] for item in options.json() if item["owner"] == owner and item["name"] == name)

    page.goto(f"{app_url}/agents")
    catalog = page.request.get(f"{api}/agents/models", headers=headers)
    assert catalog.status == 200
    models = catalog.json()
    expect(page.locator("#agent-model-options option")).to_have_count(len(models))
    assert (
        page.locator("#agent-model-options option").evaluate_all("options => options.map(option => option.value)")
        == models
    )
    assert len([model for model in models if model.startswith("opencode-zen:")]) == 83
    assert len([model for model in models if model.startswith("opencode-go:")]) == 31
    page.get_by_role("button", name="AI credentials", exact=True).click()
    credentials = page.get_by_role("dialog", name="AI credentials")
    credentials.get_by_label("Provider", exact=True).click()
    page.get_by_role("option", name="ollama", exact=True).click()
    credentials.get_by_label("Connection label").fill("CI Ollama")
    credentials.get_by_label("API key", exact=True).fill("ollama")
    credentials.get_by_role("button", name="Save connection").click()
    expect(credentials.get_by_role("button", name="Remove CI Ollama")).to_be_visible()
    credentials.locator("form").get_by_role("button", name="Close", exact=True).click()

    page.get_by_role("button", name="New environment", exact=True).first.click()
    environment = page.get_by_role("dialog", name="New environment")
    environment.get_by_label("Name", exact=True).fill("Tiny CI environment")
    environment.get_by_role("checkbox", name=repository, exact=True).check()
    environment.get_by_label("Setup script").fill(SETUP_SCRIPT)
    environment.get_by_label("Instructions").fill(
        "The supplied setup script is sufficient. No dependencies, builds, or tests are needed. "
        "If asked to edit files in a coding chat, only README.md may change."
    )
    environment.get_by_role("button", name="Create environment").click()
    expect(environment).not_to_be_visible()

    setup_command = f"cd /workspace/{repository_id} && bash .gitedge/agents/setup.sh"
    setup_prompt = (
        "Verify this tiny environment by calling run_command with "
        + json.dumps({"command": setup_command})
        + ". After it exits with code 0 and prints AGENT_SETUP_READY, reply Ready. Do not call other tools. "
        "This is the complete setup task. Do not inspect other files or edit anything."
    )
    setup = finish(page, app_url, send(page, setup_prompt))
    environments = page.request.get(f"{api}/agents/environments", headers=headers)
    assert environments.status == 200
    ready = next(item for item in environments.json() if item["name"] == "Tiny CI environment")
    assert ready["snapshot_id"] is not None

    page.get_by_role("button", name="New chat", exact=True).click()
    page.get_by_role("combobox", name="Environment", exact=True).click()
    page.get_by_role("option", name="Tiny CI environment", exact=True).click()
    edit_prompt = (
        "Update README in this tiny repository. Use run_command to create AND switch to a NEW feature branch, "
        "with a descriptive name you choose yourself. Then write README.md with the heading '# Test Repository' "
        "and the line 'Agent changed this README.'. Run git add README.md and git commit -m 'Update README'. "
        "Your shell working directory is already the repository, and Git identity is configured. "
        "Only exit code 0 means success. After the Git commit succeeds, reply Done. "
        "Do not change other files, install anything, run git push, or create a PR yet."
    )
    coding = finish(page, app_url, send(page, edit_prompt))
    assert coding.session_id != setup.session_id
    page.reload()
    expect(page.locator('article[aria-label="user message"]')).to_have_count(1)
    expect(page.locator('article[aria-label="user message"]').first).to_contain_text(
        "Update README in this tiny repository"
    )
    head_branch, committed_head = git_state(coding.session_id, repository_id)
    assert check_ref_format(Ref(f"refs/heads/{head_branch}".encode())), head_branch
    assert head_branch != "main", failure_details(coding)
    assert committed_head != base_commit, failure_details(coding)
    publication = {
        "repository": repository,
        "title": "Update README",
        "body": "Update the smoke-test README.",
        "base_branch": "main",
        "head_branch": head_branch,
    }
    publish_prompt = (
        "Call the create_pull_request tool directly with these JSON arguments: "
        + json.dumps(publication)
        + ". It is an agent tool, NOT a shell command. Do not call shell, curl, or git for this request. "
        "The tool publishes the already-committed branch through GitEdge. Return its PR URL and stop."
    )
    publication_tools.tool = "create_pull_request"
    published = finish(page, app_url, send(page, publish_prompt))
    assert published.session_id == coding.session_id
    page.reload()
    expect(page.locator('article[aria-label="user message"]')).to_have_count(2)
    expect(page.locator('article[aria-label="user message"]').first).to_contain_text(
        "Update README in this tiny repository"
    )

    pulls = page.request.get(f"{api}/repositories/{repository}/pulls", headers=headers)
    assert pulls.status == 200
    assert len(pulls.json()["data"]) == 1
    pull = pulls.json()["data"][0]
    assert pull["title"] == "Update README"
    assert pull["base_branch"] == "main"
    assert pull["head_branch"] == head_branch
    files = page.request.get(f"{api}/repositories/{repository}/pulls/{pull['number']}/files", headers=headers)
    assert files.status == 200
    assert files.json()["base_commit"] == base_commit
    assert [item["path"] for item in files.json()["files"]] == ["README.md"]
    assert files.json()["head_commit"] == committed_head

    publication_tools.tool = None
    second_command = (
        f"cd /workspace/{repository_id} && git switch {shlex.quote(head_branch)} && "
        "printf '%s\\n' '# Test Repository' '' 'Agent changed this README.' 'A second committed update.' > README.md && "
        "git add README.md && git commit -m 'Add follow-up README note' && git branch --show-current && git rev-parse HEAD"
    )
    second_prompt = (
        "Make a second real Git commit on the existing PR branch. Call run_command with "
        + json.dumps({"command": second_command})
        + ". After it succeeds, reply Done and stop. Do not publish or change other files."
    )
    second = finish(page, app_url, send(page, second_prompt))
    assert second.session_id == coding.session_id
    second_branch, second_head = git_state(coding.session_id, repository_id)
    assert second_branch == head_branch
    assert second_head not in {committed_head, base_commit}

    publication_tools.tool = "update_pull_request"
    update_prompt = (
        "Call the update_pull_request tool directly with "
        + json.dumps(
            {
                "repository": repository,
                "number": pull["number"],
                "title": "Update README",
                "body": "Update README in two Git commits.",
                "state": "open",
            }
        )
        + ". This publishes the second existing Git commit to the same PR. Do not call shell or create another PR. "
        "Keep the PR open with its original title. Return the PR URL."
    )
    updated = finish(page, app_url, send(page, update_prompt))
    assert updated.session_id == coding.session_id
    pulls = page.request.get(f"{api}/repositories/{repository}/pulls", headers=headers)
    assert pulls.status == 200
    assert len(pulls.json()["data"]) == 1
    assert pulls.json()["data"][0]["id"] == pull["id"]
    assert pulls.json()["data"][0]["title"] == "Update README"
    assert pulls.json()["data"][0]["state"] == "open"
    files = page.request.get(f"{api}/repositories/{repository}/pulls/{pull['number']}/files", headers=headers)
    assert files.status == 200
    assert files.json()["head_commit"] == second_head
    assert files.json()["base_commit"] == base_commit
    assert [item["path"] for item in files.json()["files"]] == ["README.md"]
    commits = page.request.get(f"{api}/repositories/{repository}/pulls/{pull['number']}/commits", headers=headers)
    assert commits.status == 200
    assert [item["sha"] for item in commits.json()["data"]] == [second_head, committed_head]
    page.reload()
    expect(page.locator('article[aria-label="user message"]')).to_have_count(4)

    page.get_by_role("button", name="Pin chat", exact=True).click()
    page.reload()
    expect(page.get_by_role("button", name="Unpin chat", exact=True)).to_be_visible()
    page.get_by_role("textbox", name="Search chats").fill("Update README")
    expect(page.get_by_role("button", name=re.compile("^Update README in this tiny repository"))).to_have_count(1)
    page.get_by_role("textbox", name="Search chats").fill("not-a-chat")
    expect(page.get_by_role("button", name=re.compile("^Update README in this tiny repository"))).to_have_count(0)
    page.get_by_role("textbox", name="Search chats").fill("")

    page.goto(f"{app_url}/{repository}/pulls/{pull['number']}")
    expect(page.get_by_role("heading", name=re.compile(r"^Update README #\d+$"))).to_be_visible()
    page.get_by_role("tab", name="Files Changed", exact=True).click()
    expect(page.get_by_text("README.md", exact=True).first).to_be_visible()
    expect(page.get_by_text("Agent changed this README.", exact=False).first).to_be_visible()
    expect(page.get_by_text("A second committed update.", exact=False).first).to_be_visible()

    page.get_by_role("button", name=re.compile(r"^\d+ completed or failed agent runs$")).click()
    completion = page.get_by_role("menuitem", name=re.compile("^Completed: Call the update_pull_request tool directly"))
    expect(completion).to_be_visible(timeout=30000)
    with page.expect_response(
        lambda response: response.url.endswith(f"/agents/runs/{updated.id}/read") and response.request.method == "POST"
    ) as read:
        completion.click()
    assert read.value.status == 204
    page.wait_for_url(re.compile(rf"/agents\?session={coding.session_id}$"))
    expect(page.locator('article[aria-label="user message"]')).to_have_count(4)
    notifications = page.request.get(f"{api}/agents/notifications", headers=headers)
    assert notifications.status == 200
    assert str(updated.id) not in {item["id"] for item in notifications.json()}

    with page.expect_response(
        lambda response: (
            response.url.endswith(f"/agents/sessions/{coding.session_id}") and response.request.method == "PATCH"
        )
    ) as archived:
        page.get_by_role("button", name="Archive chat", exact=True).click()
    assert archived.value.status == 200
    assert archived.value.json()["archived"] is True
    page.wait_for_url(re.compile(r"/agents$"))
    page.reload()
    expect(page.get_by_role("button", name=re.compile("^Update README in this tiny repository"))).to_have_count(0)
    remaining = page.request.get(f"{api}/agents/sessions", headers=headers)
    assert remaining.status == 200
    assert str(coding.session_id) not in {item["id"] for item in remaining.json()}
