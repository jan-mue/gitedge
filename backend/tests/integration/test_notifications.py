"""Verify notification delivery batching against PostgreSQL."""

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from app.clients.database import create_session_factory
from app.clients.notifications import SQLNotificationStore, notification_thread
from app.clients.users import SQLUserStore
from app.entities.activity import Activity, ActivityKind
from app.entities.notifications import (
    Notification,
    NotificationPreference,
    NotificationRepositoryPreference,
    NotificationSubscription,
)
from app.entities.repositories import Repository
from app.entities.users import User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def setup_audience(db: AsyncSession, size: int) -> tuple[list[User], Activity]:
    owner = await SQLUserStore(db).get_by_name("admin")
    assert owner is not None
    suffix = uuid.uuid4().hex
    users = [
        User(
            name=f"notify-{suffix}-{index}",
            lower_name=f"notify-{suffix}-{index}",
            email=f"notify-{suffix}-{index}@example.com",
            hashed_password="unused",
        )
        for index in range(size)
    ]
    repository = Repository(name=f"batch-{suffix}", owner_id=owner.id)
    db.add_all([repository, *users])
    await db.commit()
    activity = Activity(actor_id=owner.id, repo_id=repository.id, kind=ActivityKind.ISSUE_OPEN)
    db.add(activity)
    await db.commit()
    return users, activity


@pytest.mark.parametrize("size", [2, 25])
async def test_preferences_and_notifications_are_batched(infrastructure: dict[str, str], size: int) -> None:
    engine = create_async_engine(infrastructure["DATABASE_URL"])
    try:
        async with create_session_factory(engine)() as db:
            users, activity = await setup_audience(db, size)
            db.add_all(
                [
                    NotificationPreference(user_id=users[0].id, email=True),
                    NotificationRepositoryPreference(
                        user_id=users[0].id, repo_id=activity.repo_id, categories=["issue"]
                    ),
                    NotificationSubscription(
                        user_id=users[1].id, repo_id=activity.repo_id, thread=notification_thread(activity), muted=True
                    ),
                ]
            )
            await db.commit()
            statements = []
            commits = []

            def record_statement(
                _connection: object,
                _cursor: object,
                statement: str,
                _parameters: object,
                _context: object,
                _executemany: bool,
            ) -> None:
                statements.append(statement)

            event.listen(engine.sync_engine, "before_cursor_execute", record_statement)
            event.listen(db.sync_session, "after_commit", lambda _session: commits.append(True))
            store = SQLNotificationStore(db)
            preferences = await store.delivery_preferences([user.id for user in users], activity)
            assert len(statements) == 3
            assert preferences[users[0].id].email is True
            assert preferences[users[0].id].categories == ["issue"]
            assert preferences[users[1].id].muted is True
            assert preferences[users[1].id].email is False
            entries = [
                Notification(user_id=user.id, activity_id=activity.id, category="issue", reason="subscribed")
                for user in users
            ]
            await store.add_many(entries)
            assert len(statements) == 4  # Three preference reads and one batched INSERT, independent of audience size.
            assert len(commits) == 1
            assert len({entry.id for entry in entries}) == size
            assert all(entry.created_at is not None for entry in entries)
            assert (
                await db.scalar(
                    select(func.count()).select_from(Notification).where(Notification.activity_id == activity.id)
                )
                == size
            )
    finally:
        await engine.dispose()


async def test_notification_batch_rolls_back_together(infrastructure: dict[str, str]) -> None:
    engine = create_async_engine(infrastructure["DATABASE_URL"])
    try:
        async with create_session_factory(engine)() as db:
            users, activity = await setup_audience(db, 2)
            entries = [
                Notification(user_id=user.id, activity_id=activity.id, category="issue", reason="subscribed")
                for user in users
            ]
            entries.append(
                Notification(user_id=uuid.uuid4(), activity_id=activity.id, category="issue", reason="subscribed")
            )
            with pytest.raises(IntegrityError):
                await SQLNotificationStore(db).add_many(entries)
            await db.rollback()
            assert await db.scalar(select(func.count()).select_from(Notification)) == 0
    finally:
        await engine.dispose()


async def test_notification_batches_suppress_duplicate_deliveries(infrastructure: dict[str, str]) -> None:
    engine = create_async_engine(infrastructure["DATABASE_URL"])
    try:
        async with create_session_factory(engine)() as db:
            users, activity = await setup_audience(db, 2)
            store = SQLNotificationStore(db)
            entries = [
                Notification(user_id=user.id, activity_id=activity.id, category="workflow", reason="triggered")
                for user in [*users, users[0]]
            ]
            inserted = await store.add_many(entries)
            assert len(inserted) == 2
            assert all(entry.created_at and entry.updated_at for entry in inserted)
            assert all(entry.is_read is False and entry.is_archived is False for entry in inserted)
            assert await store.add_many(entries) == []
            assert (
                await db.scalar(
                    select(func.count()).select_from(Notification).where(Notification.activity_id == activity.id)
                )
                == 2
            )
    finally:
        await engine.dispose()
