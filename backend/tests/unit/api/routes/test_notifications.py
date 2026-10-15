"""Notification delivery and recipient isolation tests."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.api.dependencies import get_email_client
from app.clients.email import SMTPClient
from app.config import settings
from app.entities.repositories import Repository
from app.index import app
from app.services.notifications import mentioned_users

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from pytest_mock import MockerFixture

    from tests.unit.utils.fakes import FakeStores

PREFIX = settings.API_V1_STR
URL = f"{PREFIX}/notifications"
OWNER = settings.FIRST_SUPERUSER.split("@")[0]
REPO = f"{PREFIX}/repositories/{OWNER}/notifications-test"


def inbox(client: TestClient, headers: dict[str, str], **params: str | int) -> dict:
    return client.get(f"{URL}/", headers=headers, params=params).json()


@pytest.mark.parametrize("target", ["issues", "pulls"])
def test_discussion_lifecycle(
    client: TestClient, superuser_token_headers: dict[str, str], normal_user_token_headers: dict[str, str], target: str
) -> None:
    response = client.post(
        f"{REPO}/{target}",
        headers=normal_user_token_headers,
        json={"title": "Track activity", "head_branch": "feature"},
    )
    assert response.status_code == 201
    number = response.json()["number"]
    assert inbox(client, normal_user_token_headers)["count"] == 0
    for state in ["closed", "open"]:
        assert (
            client.patch(
                f"{REPO}/{target}/{number}", headers=normal_user_token_headers, json={"state": state}
            ).status_code
            == 200
        )
    if target == "pulls":
        client.patch(f"{REPO}/pulls/{number}", headers=normal_user_token_headers, json={"state": "merged"})
    result = inbox(client, superuser_token_headers)
    assert result["count"] == (4 if target == "pulls" else 3)
    assert all(n["url"] == f"/{OWNER}/notifications-test/{target}/{number}" for n in result["data"])
    client.patch(
        f"{REPO}/{target}/{number}",
        headers=normal_user_token_headers,
        json={"state": "merged" if target == "pulls" else "open"},
    )
    assert inbox(client, superuser_token_headers)["count"] == result["count"]
    client.post(f"{REPO}/issues/{number}/comments", headers=superuser_token_headers, json={"body": "Reply"})
    authored = inbox(client, normal_user_token_headers)["data"]
    assert len(authored) == 1
    assert authored[0]["reason"] == "author"
    assert "#comment-" in authored[0]["url"]


def test_mentions_and_edits(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    fake_stores: FakeStores,
) -> None:
    normal = next(user for user in fake_stores.users.items.values() if not user.is_superuser)
    response = client.post(
        f"{REPO}/issues",
        headers=superuser_token_headers,
        json={"title": "Mention", "body": f"@{normal.name.upper()} @{normal.name}"},
    )
    number = response.json()["number"]
    data = inbox(client, normal_user_token_headers, reason="mentioned")["data"]
    assert len(data) == 1
    assert data[0]["category"] == "mention"
    client.patch(
        f"{REPO}/issues/{number}", headers=superuser_token_headers, json={"body": f"@{normal.name} same mention"}
    )
    assert inbox(client, normal_user_token_headers)["count"] == 1
    comment = client.post(
        f"{REPO}/issues/{number}/comments", headers=superuser_token_headers, json={"body": "No mention"}
    ).json()
    client.patch(
        f"{PREFIX}/comments/{comment['id']}", headers=superuser_token_headers, json={"body": f"Now @{normal.name}"}
    )
    assert inbox(client, normal_user_token_headers)["count"] == 2


def test_inbox_actions_and_ownership(
    client: TestClient, superuser_token_headers: dict[str, str], normal_user_token_headers: dict[str, str]
) -> None:
    client.post(f"{REPO}/issues", headers=normal_user_token_headers, json={"title": "Searchable"})
    n = inbox(client, superuser_token_headers)["data"][0]
    assert inbox(client, superuser_token_headers, query="SEARCHABLE")["count"] == 1
    assert inbox(client, superuser_token_headers, query="missing")["count"] == 0
    for headers, ids in [
        (normal_user_token_headers, [n["id"]]),
        (superuser_token_headers, [n["id"], str(uuid.uuid4())]),
    ]:
        assert client.patch(f"{URL}/", headers=headers, json={"ids": ids, "is_read": True}).status_code == 404
    assert inbox(client, superuser_token_headers)["unread_count"] == 1
    assert (
        client.patch(
            f"{URL}/", headers=superuser_token_headers, json={"ids": [n["id"]], "is_archived": True}
        ).status_code
        == 204
    )
    assert inbox(client, superuser_token_headers)["count"] == 0
    assert inbox(client, superuser_token_headers)["unread_count"] == 0
    assert inbox(client, superuser_token_headers, view="archived")["data"][0]["is_read"] is True
    client.patch(f"{URL}/", headers=superuser_token_headers, json={"ids": [n["id"]], "is_archived": False})
    assert inbox(client, superuser_token_headers, read="unread")["count"] == 0
    assert inbox(client, superuser_token_headers, read="unread", focus=n["id"])["count"] == 1
    assert client.get(f"{URL}/").status_code == 401


def test_subscriptions_and_categories(
    client: TestClient, superuser_token_headers: dict[str, str], normal_user_token_headers: dict[str, str]
) -> None:
    issue = client.post(f"{REPO}/issues", headers=normal_user_token_headers, json={"title": "Muted"}).json()
    n = inbox(client, superuser_token_headers)["data"][0]
    client.patch(f"{URL}/", headers=superuser_token_headers, json={"ids": [n["id"]], "unsubscribed": True})
    client.post(f"{REPO}/issues/{issue['number']}/comments", headers=normal_user_token_headers, json={"body": "Muted"})
    assert inbox(client, superuser_token_headers)["count"] == 1
    assert inbox(client, superuser_token_headers)["data"][0]["unsubscribed"] is True
    client.patch(f"{URL}/", headers=superuser_token_headers, json={"ids": [n["id"]], "unsubscribed": False})
    client.post(
        f"{REPO}/issues/{issue['number']}/comments", headers=normal_user_token_headers, json={"body": "Subscribed"}
    )
    assert inbox(client, superuser_token_headers)["count"] == 2
    preferences = f"{URL}/repositories/{OWNER}/notifications-test"
    assert (
        client.put(preferences, headers=superuser_token_headers, json={"categories": ["pull", "mention"]}).status_code
        == 200
    )
    client.post(f"{REPO}/issues", headers=normal_user_token_headers, json={"title": "Disabled category"})
    assert inbox(client, superuser_token_headers)["count"] == 2
    assert client.get(preferences, headers=normal_user_token_headers).json()["categories"] != ["pull", "mention"]


def test_reactions_notify_once(
    client: TestClient, superuser_token_headers: dict[str, str], normal_user_token_headers: dict[str, str]
) -> None:
    issue = client.post(f"{REPO}/issues", headers=superuser_token_headers, json={"title": "Reactions"}).json()
    comment = client.post(
        f"{REPO}/issues/{issue['number']}/comments", headers=superuser_token_headers, json={"body": "React"}
    ).json()
    url = f"{PREFIX}/comments/{comment['id']}/reactions"
    for _ in range(2):
        assert client.put(url, headers=normal_user_token_headers, json={"emoji": "👍"}).json() == {
            "data": [{"emoji": "👍", "count": 1, "reacted": True}]
        }
    entries = inbox(client, superuser_token_headers)["data"]
    assert len(entries) == 1
    assert entries[0]["kind"] == "reaction"
    assert entries[0]["reason"] == "reaction"
    assert entries[0]["url"].endswith(f"#comment-{comment['id']}")
    assert client.get(url, headers=superuser_token_headers).json()["data"][0]["reacted"] is False
    assert client.request("DELETE", url, headers=normal_user_token_headers, json={"emoji": "👍"}).json() == {"data": []}
    assert client.put(url, headers=normal_user_token_headers, json={"emoji": "invalid"}).status_code == 422


def test_private_repository_does_not_leak(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    fake_stores: FakeStores,
) -> None:
    normal = next(user for user in fake_stores.users.items.values() if not user.is_superuser)
    owner = next(user for user in fake_stores.users.items.values() if user.is_superuser)
    repository = Repository(name="private-notifications", owner_id=owner.id, is_private=True)
    fake_stores.repository.persist(repository)
    url = f"{PREFIX}/repositories/{owner.name}/{repository.name}"
    client.put(f"{url}/watch", headers=normal_user_token_headers)
    client.post(f"{url}/issues", headers=superuser_token_headers, json={"title": "Secret", "body": f"@{normal.name}"})
    assert inbox(client, normal_user_token_headers)["count"] == 0
    assert (
        client.get(f"{URL}/repositories/{owner.name}/{repository.name}", headers=normal_user_token_headers).status_code
        == 404
    )


def test_email_is_opt_in_and_keeps_inbox(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    mocker: MockerFixture,
) -> None:
    mocker.patch.object(settings, "SMTP_HOST", "smtp.example.test")
    mocker.patch.object(settings, "EMAILS_FROM_EMAIL", "notifications@example.test")
    email = mocker.Mock()
    app.dependency_overrides[get_email_client] = lambda: email
    try:
        client.post(f"{REPO}/issues", headers=normal_user_token_headers, json={"title": "Inbox only"})
        email.send_email.assert_not_called()
        assert (
            client.put(f"{URL}/preferences", headers=superuser_token_headers, json={"email": True}).json()["email"]
            is True
        )
        client.post(f"{REPO}/issues", headers=normal_user_token_headers, json={"title": "Email <script>"})
        assert email.send_email.call_count == 1
        html = email.send_email.call_args.args[2]
        assert "&lt;script&gt;" in html
        assert "from=notifications" in html
        assert inbox(client, superuser_token_headers)["count"] == 2
        assert client.get(f"{URL}/preferences", headers=normal_user_token_headers).json()["email"] is False
        email.send_email.side_effect = RuntimeError("SMTP unavailable")
        assert (
            client.post(f"{REPO}/issues", headers=normal_user_token_headers, json={"title": "SMTP failure"}).status_code
            == 201
        )
        assert inbox(client, superuser_token_headers)["count"] == 3
        client.put(f"{URL}/preferences", headers=superuser_token_headers, json={"email": False})
        client.post(f"{REPO}/issues", headers=normal_user_token_headers, json={"title": "Email disabled"})
        assert email.send_email.call_count == 2
    finally:
        app.dependency_overrides.pop(get_email_client, None)


def test_mention_parser() -> None:
    assert mentioned_users(
        "@Alice @alice test@bob.com `@inline` ```\n@fenced\n``` https://example.com/@url @real-user"
    ) == {"alice", "real-user"}


def test_watchers_and_participants_receive_activity(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    client.put(f"{REPO}/watch", headers=normal_user_token_headers)
    client.post(f"{REPO}/issues", headers=superuser_token_headers, json={"title": "Watched"})
    assert inbox(client, normal_user_token_headers)["data"][0]["reason"] == "subscribed"
    client.delete(f"{REPO}/watch", headers=normal_user_token_headers)
    issue = client.post(f"{REPO}/issues", headers=superuser_token_headers, json={"title": "Not watched"}).json()
    assert inbox(client, normal_user_token_headers)["count"] == 1
    client.post(
        f"{REPO}/issues/{issue['number']}/comments", headers=normal_user_token_headers, json={"body": "Participating"}
    )
    client.post(f"{REPO}/issues/{issue['number']}/comments", headers=superuser_token_headers, json={"body": "Reply"})
    assert inbox(client, normal_user_token_headers)["data"][0]["reason"] == "participating"


def test_pagination_counts_and_mark_all_read(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    for title in ["First", "Second", "Third"]:
        client.post(f"{REPO}/issues", headers=normal_user_token_headers, json={"title": title})
    page = inbox(client, superuser_token_headers, limit=1, offset=1)
    assert len(page["data"]) == 1
    assert page["count"] == 3
    assert page["unread_count"] == 3
    assert page["repository_counts"] == {f"{OWNER}/notifications-test": 3}
    assert client.post(f"{URL}/read-all", headers=superuser_token_headers).status_code == 204
    assert inbox(client, superuser_token_headers)["unread_count"] == 0
    assert (
        client.post(
            f"{URL}/repositories/{OWNER}/notifications-test/archive", headers=superuser_token_headers
        ).status_code
        == 204
    )
    assert inbox(client, superuser_token_headers)["count"] == 0
    assert inbox(client, superuser_token_headers, view="archived")["count"] == 3


def test_only_published_releases_notify(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    response = client.post(
        f"{REPO}/releases",
        headers=normal_user_token_headers,
        json={"tag_name": "v1.0.0", "name": "Release preview", "is_draft": True},
    )
    assert response.status_code == 201
    assert inbox(client, superuser_token_headers)["count"] == 0
    assert (
        client.patch(f"{REPO}/releases/v1.0.0", headers=normal_user_token_headers, json={"is_draft": False}).status_code
        == 200
    )
    assert inbox(client, superuser_token_headers)["data"][0]["category"] == "release"
    client.patch(f"{REPO}/releases/v1.0.0", headers=normal_user_token_headers, json={"is_draft": False})
    assert inbox(client, superuser_token_headers)["count"] == 1


def test_smtp_rejection_is_reported(mocker: MockerFixture) -> None:
    mocker.patch.object(settings, "SMTP_HOST", "smtp.example.test")
    mocker.patch.object(settings, "EMAILS_FROM_EMAIL", "notifications@example.test")
    message = mocker.patch("app.clients.email.Message")
    message.return_value.send.return_value.success = False
    message.return_value.send.return_value.status_code = 550
    with pytest.raises(RuntimeError, match="SMTP delivery failed with status 550"):
        SMTPClient().send_email("recipient@example.com", "Notification", "<p>Activity</p>")
