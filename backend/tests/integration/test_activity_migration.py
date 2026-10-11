"""Legacy comment activity repair against PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.entities.activity import Activity, ActivityKind, ActivityTargetType
from app.entities.comments import Comment
from app.entities.issues import Issue
from app.entities.repositories import Repository
from app.entities.users import User
from tests.integration.conftest import FIRST_SUPERUSER, run_migration_upgrade


@pytest.mark.parametrize(
    "case",
    [
        "sequential",
        "already_linked",
        "deleted_reply",
        "overlapping",
        "event_before_reply",
        "mismatched_reference",
        "wrong_target",
        "extra_reply",
        "wrong_author",
        "duplicate_time",
        "different_authors",
        "different_discussions",
    ],
)
def test_restore_legacy_comment_links(infrastructure: dict[str, str], case: str) -> None:
    """Repair complete, unambiguous histories without reassigning existing or deleted replies."""
    engine = create_engine(infrastructure["DATABASE_URL"])
    try:
        with Session(engine) as session:
            owner = session.scalar(select(User).where(User.name == FIRST_SUPERUSER.split("@")[0]))
            assert owner is not None
            repo = Repository(name="legacy-repair", owner_id=owner.id)
            session.add(repo)
            session.flush()
            issues = [
                Issue(repo_id=repo.id, author_id=owner.id, number=number, title=f"Issue {number}", body="Description")
                for number in [1, 2]
            ]
            session.add_all(issues)
            session.flush()
            start = datetime(2020, 1, 1, tzinfo=UTC)
            replies = [
                Comment(
                    issue_id=issues[0].id,
                    author_id=owner.id,
                    body=f"Reply {index}",
                    created_at=start + timedelta(seconds=10 * index),
                )
                for index in range(2)
            ]
            events = [
                Activity(
                    actor_id=owner.id,
                    repo_id=repo.id,
                    kind=ActivityKind.COMMENT,
                    target_type=ActivityTargetType.ISSUE,
                    target_number=1,
                    created_at=start + timedelta(seconds=10 * index + 1),
                )
                for index in range(2)
            ]
            if case in {"wrong_author", "different_authors"}:
                suffix = uuid.uuid4().hex
                other = User(
                    name=f"repair-{suffix}",
                    lower_name=f"repair-{suffix}",
                    email=f"repair-{suffix}@example.com",
                    hashed_password="unused",
                )
                session.add(other)
                session.flush()
                replies[1].author_id = other.id
                if case == "different_authors":
                    events[1].actor_id = other.id
            replies[1].created_at = {
                "overlapping": start + timedelta(milliseconds=500),
                "duplicate_time": start,
            }.get(case, replies[1].created_at)
            if case == "event_before_reply":
                events[0].created_at = start - timedelta(seconds=1)
            if case == "wrong_target":
                events[1].target_type = ActivityTargetType.PULL_REQUEST
            if case == "different_discussions":
                replies[1].issue_id = issues[1].id
                events[1].target_number = 2
            session.add_all(replies)
            session.flush()
            if case == "already_linked":
                events[0].comment_id = replies[0].id
            if case == "mismatched_reference":
                events[0].comment_id = replies[1].id
            if case == "deleted_reply":
                session.delete(replies[0])
            if case == "extra_reply":
                session.add(
                    Comment(
                        issue_id=issues[0].id,
                        author_id=owner.id,
                        body="Unrecorded reply",
                        created_at=start + timedelta(seconds=20),
                    )
                )
            session.add_all(events)
            session.flush()
            expected = {event.id: event.comment_id for event in events}
            if case in {"sequential", "already_linked", "different_authors", "different_discussions"}:
                expected = {event.id: reply.id for event, reply in zip(events, replies, strict=True)}
            timestamps = {event.id: event.created_at for event in events}
            session.commit()

        for _ in range(2):
            run_migration_upgrade("ececc099d6b5")
            with Session(engine) as session:
                actual = dict(
                    session.execute(select(Activity.id, Activity.comment_id).where(Activity.id.in_(expected))).all()
                )
                assert actual == expected
                assert (
                    dict(
                        session.execute(select(Activity.id, Activity.created_at).where(Activity.id.in_(expected))).all()
                    )
                    == timestamps
                )
    finally:
        engine.dispose()
