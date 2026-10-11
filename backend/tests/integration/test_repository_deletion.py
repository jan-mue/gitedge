from __future__ import annotations

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine

from app.clients.activity import SQLActivityStore
from app.clients.comments import SQLCommentStore
from app.clients.database import create_session_factory
from app.clients.issues import SQLIssueStore
from app.clients.repositories import SQLRepositoryStore
from app.clients.users import SQLUserStore
from app.entities.activity import Activity, ActivityKind
from app.entities.comments import Comment
from app.entities.issues import Issue
from app.entities.repositories import Repository
from tests.integration.conftest import _run_async


@pytest.mark.parametrize("fail", [False, True])
def test_repository_deletion_transaction(infrastructure: dict[str, str], fail: bool) -> None:
    _run_async(_check_repository_deletion(infrastructure, fail))


async def _check_repository_deletion(infrastructure: dict[str, str], fail: bool) -> None:
    engine = create_async_engine(infrastructure["DATABASE_URL"])
    factory = create_session_factory(engine)
    try:
        async with factory() as db:
            user = await SQLUserStore(db).get_by_name("admin")
            assert user is not None
            store = SQLRepositoryStore(db)
            repository = Repository(name="delete-transaction", owner_id=user.id)
            await store.add(repository)
            fork = Repository(name="surviving-fork", owner_id=user.id, fork_of_id=repository.id)
            await store.add(fork)
            issue = Issue(repo_id=repository.id, author_id=user.id, number=1, title="Issue")
            await SQLIssueStore(db).add(issue)
            comment = Comment(issue_id=issue.id, author_id=user.id, body="Reply")
            await SQLCommentStore(db).add(comment)
            activity = Activity(
                actor_id=user.id, repo_id=repository.id, kind=ActivityKind.COMMENT, comment_id=comment.id
            )
            await SQLActivityStore(db).add(activity)
            repository = await store.get_by_owner_and_name("admin", repository.name)
            assert db.in_transaction()

            def fail_delete(
                _connection: object,
                _cursor: object,
                statement: str,
                _parameters: object,
                _context: object,
                _executemany: bool,
            ) -> None:
                if statement.startswith("DELETE FROM repository"):
                    raise RuntimeError("Deletion failed")

            if fail:
                event.listen(engine.sync_engine, "before_cursor_execute", fail_delete)
                try:
                    with pytest.raises(RuntimeError, match="Deletion failed"):
                        await store.delete(repository)
                finally:
                    event.remove(engine.sync_engine, "before_cursor_execute", fail_delete)
            else:
                await store.delete(repository)
            assert repository.owner.name == "admin"

            async with factory() as observer:
                for entity in (repository, issue, comment, activity):
                    assert (await observer.get(type(entity), entity.id) is not None) == fail
                surviving_fork = await observer.get(Repository, fork.id)
                assert surviving_fork is not None
                assert surviving_fork.fork_of_id == (repository.id if fail else None)
    finally:
        await engine.dispose()
