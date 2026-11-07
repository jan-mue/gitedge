from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from fastapi import BackgroundTasks

from app.clients.email import EmailClient
from app.config import settings
from app.entities.actions import WorkflowRun
from app.entities.watchers import Watcher
from app.schemas.actions import ActionJob
from app.schemas.authorization import RepositoryCollaborator
from app.services.actions.notifications import WorkflowFailureNotifications
from app.services.activity import ActivityService
from app.services.authorization import AuthorizationService
from app.services.notifications import NotificationService, activity_url
from tests.unit.api.routes.test_authorization import add_repository, add_user
from tests.unit.services.test_actions_dispatch import Execution, add_run, pending
from tests.unit.services.test_actions_dispatch import execution as execution  # noqa: PLC0414 — pytest fixture re-export

if TYPE_CHECKING:
    from pytest_mock import MockerFixture, MockType

    from tests.unit.utils.fakes import FakeStores

type Failure = tuple[WorkflowFailureNotifications, WorkflowRun, BackgroundTasks, MockType]


@pytest.fixture
async def failure(fake_stores: FakeStores, mocker: MockerFixture) -> Failure:
    owner, actor = add_user(fake_stores, "owner"), add_user(fake_stores, "actor")
    watcher, outsider = add_user(fake_stores, "watcher"), add_user(fake_stores, "outsider")
    repo = add_repository(fake_stores, owner)
    for user in (actor, watcher):
        await fake_stores.authorization.save(
            RepositoryCollaborator(repository_id=repo.id, user_id=user.id, role="read")
        )
    for user in (watcher, outsider):
        fake_stores.watchers.persist(Watcher(repo_id=repo.id, user_id=user.id))
    authorization = AuthorizationService(
        fake_stores.authorization, fake_stores.repository, fake_stores.organizations, fake_stores.users
    )
    tasks, email = BackgroundTasks(), mocker.Mock(spec=EmailClient)
    delivery = NotificationService(fake_stores.notifications, fake_stores.repository, email, tasks, authorization)
    activity = ActivityService(fake_stores.activity, fake_stores.repository, fake_stores.stars, authorization, delivery)
    service = WorkflowFailureNotifications(activity, fake_stores.repository, fake_stores.users)
    run = WorkflowRun(
        id=uuid.uuid4(),
        repo_id=repo.id,
        name="CI",
        status="failure",
        actor=actor.name,
        event_name="push",
        event={"sender": (await service.actor(actor.name)).model_dump(mode="json")},
        jobs=[ActionJob(id="test", key="test", name="Test", status="failure").model_dump(mode="json")],
    )
    mocker.patch.object(settings, "SMTP_HOST", "smtp.example.com")
    mocker.patch.object(settings, "EMAILS_FROM_EMAIL", "notifications@example.com")
    fake_stores.notifications.email_preferences[actor.id] = True
    return service, run, tasks, email


async def test_final_failure_notifies_initiator_and_visible_watchers_once(
    failure: Failure, fake_stores: FakeStores
) -> None:
    service, run, tasks, email = failure
    actor = next(user for user in fake_stores.users.items.values() if user.name == "actor")
    actor.name = actor.lower_name = "renamed"
    await service.notify(run)
    await service.notify(run)
    assert len(fake_stores.activity.items) == 1
    assert len(fake_stores.notifications.items) == 3
    recipients = {fake_stores.users.items[n.user_id].name for n in fake_stores.notifications.items.values()}
    assert recipients == {"owner", "renamed", "watcher"}
    activity = next(iter(fake_stores.activity.items.values()))
    assert activity.title == "CI failed: Test"
    assert activity_url(activity) == f"/owner/repo/actions?run={run.id}"
    await tasks()
    email.send_email.assert_called_once()
    html = email.send_email.call_args.args[2]
    assert f"run={run.id}&amp;from=notifications" in html


@pytest.mark.parametrize("status", ["queued", "running", "success", "cancelled", "skipped"])
async def test_only_final_failures_notify(failure: Failure, fake_stores: FakeStores, status: str) -> None:
    service, run, _, _ = failure
    run.status = status
    await service.notify(run)
    assert not fake_stores.activity.items
    assert not fake_stores.notifications.items


async def test_failure_delivery_respects_category_mute_and_current_access(
    failure: Failure, fake_stores: FakeStores
) -> None:
    service, run, tasks, email = failure
    actor = next(user for user in fake_stores.users.items.values() if user.name == "actor")
    owner = next(user for user in fake_stores.users.items.values() if user.name == "owner")
    fake_stores.notifications.repository_preferences[(actor.id, run.repo_id)] = []
    fake_stores.notifications.muted.add((owner.id, run.repo_id, f"workflow_run:{run.id}"))
    fake_stores.authorization.items.clear()
    await service.notify(run)
    assert not fake_stores.notifications.items
    await tasks()
    email.send_email.assert_not_called()


async def test_invalid_workflow_without_attempts_has_a_durable_retryable_notification(
    execution: Execution, mocker: MockerFixture
) -> None:
    service, store, _, _ = execution
    run = await add_run(execution)
    async with store.transaction(run.id) as state:
        assert state is not None
        state.run.status = "failure"
        state.jobs.clear()
        state.attempts.clear()
    message = pending(store, "notify")[0]
    assert message.attempt_id is None
    notify = mocker.AsyncMock(side_effect=TimeoutError("notification database unavailable"))
    mocker.patch.object(service.notifications, "notify", notify)
    with pytest.raises(TimeoutError):
        await service.dispatcher.deliver(message)
    assert message.acknowledged_at is None
    notify.side_effect = None
    await service.dispatcher.deliver(message)
    await service.dispatcher.deliver(message)
    assert notify.await_count == 2
    assert message.acknowledged_at is not None
    assert len([m for m in store.messages.values() if m.kind == "notify"]) == 1
