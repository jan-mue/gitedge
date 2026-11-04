"""Verify notification delivery through the API, PostgreSQL, and Mailpit SMTP."""

from __future__ import annotations

import time
import uuid
from html import unescape
from typing import Any

import httpx2

from app.config import settings
from tests.conftest import create_user_via_api


def login(client: httpx2.Client, email: str, password: str) -> dict[str, str]:
    response = client.post("/login/access-token", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def messages_for(mailpit: httpx2.Client, recipient: str) -> list[dict[str, Any]]:
    response = mailpit.get("/api/v1/search", params={"query": f"to:{recipient}"})
    response.raise_for_status()
    return response.json()["messages"]


def wait_for_messages(mailpit: httpx2.Client, recipient: str, count: int) -> list[dict[str, Any]]:
    deadline = time.monotonic() + 10
    messages = messages_for(mailpit, recipient)
    while len(messages) < count and time.monotonic() < deadline:
        time.sleep(0.1)
        messages = messages_for(mailpit, recipient)
    assert len(messages) == count, f"Expected {count} emails for {recipient}, found {messages}"
    return messages


def test_notification_emails_reach_smtp_catcher(
    app_url: str, mailpit_http_url: str, infrastructure: dict[str, str]
) -> None:
    suffix = uuid.uuid4().hex[:12]
    password = f"notification-test-{suffix}"
    owner_email = f"owner-{suffix}@example.com"
    opted_in_email = f"email-{suffix}@example.com"
    inbox_only_email = f"inbox-{suffix}@example.com"
    owner = create_user_via_api(app_url, owner_email, password)["name"]
    for email in (opted_in_email, inbox_only_email):
        create_user_via_api(app_url, email, password)
    repository = f"notifications-{suffix}"
    repo_path = f"/repositories/{owner}/{repository}"
    title = "Fix <script>alert('unsafe')</script> & retry"

    with (
        httpx2.Client(base_url=f"{app_url}/api/v1", timeout=10) as api,
        httpx2.Client(base_url=mailpit_http_url, timeout=5) as mailpit,
    ):
        owner_headers = login(api, owner_email, password)
        opted_in_headers = login(api, opted_in_email, password)
        inbox_only_headers = login(api, inbox_only_email, password)
        created = api.post("/repositories/", json={"owner": owner, "name": repository})
        assert created.status_code == 201, created.text
        for headers in (opted_in_headers, inbox_only_headers):
            watched = api.put(f"{repo_path}/watch", headers=headers)
            assert watched.status_code == 200, watched.text
            preferences = api.get("/notifications/preferences", headers=headers)
            assert preferences.json() == {"email": False, "email_available": True}
        opted_in = api.put("/notifications/preferences", headers=opted_in_headers, json={"email": True})
        assert opted_in.status_code == 200, opted_in.text
        assert opted_in.json()["email"] is True

        issue = api.post(f"{repo_path}/issues", headers=owner_headers, json={"title": title})
        assert issue.status_code == 201, issue.text
        number = issue.json()["number"]
        first_messages = wait_for_messages(mailpit, opted_in_email, 1)
        first_id = first_messages[0]["ID"]

        comment = api.post(
            f"{repo_path}/issues/{number}/comments", headers=owner_headers, json={"body": "Please review"}
        )
        assert comment.status_code == 201, comment.text
        captured = wait_for_messages(mailpit, opted_in_email, 2)
        assert len({message["ID"] for message in captured}) == 2

        inbox = api.get("/notifications/", headers=opted_in_headers, params={"query": title})
        assert inbox.status_code == 200, inbox.text
        assert inbox.json()["count"] == 2
        entries = {entry["kind"]: entry for entry in inbox.json()["data"]}
        assert set(entries) == {"issue_open", "comment"}
        for message in captured:
            detail = mailpit.get(f"/api/v1/message/{message['ID']}")
            detail.raise_for_status()
            delivered = detail.json()
            assert delivered["To"] == [{"Name": "", "Address": opted_in_email}]
            assert delivered["From"]["Address"] == infrastructure["EMAILS_FROM_EMAIL"]
            assert delivered["Subject"] == f"[{owner}/{repository}] {title}"
            html = delivered["HTML"]
            assert "&lt;script&gt;" in html
            assert "<script>" not in html
            assert f"{owner}: " in html
            kind = "issue_open" if message["ID"] == first_id else "comment"
            assert kind.replace("_", " ") in html
            entry = entries[kind]
            destination = (
                f"{settings.FRONTEND_HOST.rstrip('/')}/{owner}/{repository}/issues/{number}"
                f"?from=notifications&n={entry['id']}"
            )
            if kind == "comment":
                destination += f"#comment-{comment.json()['id']}"
            assert f'href="{destination}"' in unescape(html)
            assert f"{settings.FRONTEND_HOST.rstrip('/')}/settings?tab=notifications" in unescape(html)

        inbox_only = api.get("/notifications/", headers=inbox_only_headers, params={"query": title})
        assert inbox_only.status_code == 200, inbox_only.text
        assert inbox_only.json()["count"] == 2
        assert messages_for(mailpit, inbox_only_email) == []
        assert messages_for(mailpit, owner_email) == []
