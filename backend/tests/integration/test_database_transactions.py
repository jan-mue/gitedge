from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi import Depends, FastAPI, HTTPException, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.dependencies import RepositoryStoreDep, SessionDep, get_activity_store, get_current_user
from app.api.routes.comments import router as comments_router
from app.clients.activity import SQLActivityStore
from app.clients.database import create_session_factory
from app.clients.issues import SQLIssueStore
from app.clients.repositories import SQLRepositoryStore
from app.clients.users import SQLUserStore
from app.entities.activity import Activity
from app.entities.comments import Comment
from app.entities.issues import Issue
from app.entities.repositories import Repository

if TYPE_CHECKING:
    import uuid
    from collections.abc import AsyncIterator

    from sqlalchemy.orm import Session

    from app.entities.users import User


@pytest.fixture
async def transaction_app(infrastructure: dict[str, str]) -> AsyncIterator[FastAPI]:
    engine = create_async_engine(infrastructure["DATABASE_URL"])
    factory = create_session_factory(engine)

    def configure_session(request: Request) -> None:
        request.state.db_session_factory = factory

    app = FastAPI(dependencies=[Depends(configure_session)])
    app.state.db_session_factory = factory
    app.include_router(comments_router)

    async def current_user(db: SessionDep) -> User:
        user = await SQLUserStore(db).get_by_name("admin")
        assert user is not None
        return user

    app.dependency_overrides[get_current_user] = current_user

    @app.delete("/repositories/{name}")
    async def delete_repository(name: str, store: RepositoryStoreDep, fail: bool = False) -> None:
        repository = await store.get_by_owner_and_name("admin", name)
        await store.delete(repository)
        if fail:
            raise HTTPException(status_code=409, detail="Abort transaction")

    try:
        yield app
    finally:
        await engine.dispose()


async def _seed_repository(factory: async_sessionmaker[AsyncSession]) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    async with factory.begin() as db:
        user = await SQLUserStore(db).get_by_name("admin")
        assert user is not None
        store = SQLRepositoryStore(db)
        repository = Repository(name="transactions", owner_id=user.id)
        await store.add(repository)
        fork = Repository(name="transaction-fork", owner_id=user.id, fork_of_id=repository.id)
        await store.add(fork)
        issue = Issue(repo_id=repository.id, author_id=user.id, number=1, title="Transaction test")
        await SQLIssueStore(db).add(issue)
        return repository.id, fork.id, issue.id


@pytest.mark.parametrize("failure", [None, "activity", "commit"])
async def test_comment_and_activity_commit_together(transaction_app: FastAPI, failure: str | None) -> None:
    factory = transaction_app.state.db_session_factory
    repository_id, _, issue_id = await _seed_repository(factory)

    if failure is not None:

        def fail_commit(_db: Session) -> None:
            raise RuntimeError("Commit failed")

        class FailingActivityStore(SQLActivityStore):
            async def add(self, obj: Activity) -> None:
                await super().add(obj)
                if failure == "activity":
                    raise RuntimeError("Activity recording failed")
                event.listen(self.db.sync_session, "before_commit", fail_commit, once=True)

        def failing_activity_store(db: SessionDep) -> FailingActivityStore:
            return FailingActivityStore(db)

        transaction_app.dependency_overrides[get_activity_store] = failing_activity_store

    async with AsyncClient(
        transport=ASGITransport(app=transaction_app, raise_app_exceptions=False), base_url="http://test"
    ) as client:
        response = await client.post("/repositories/admin/transactions/issues/1/comments", json={"body": "Reply"})

    assert response.status_code == (500 if failure is not None else 201)
    async with factory() as db:
        comments = list(await db.scalars(select(Comment).where(Comment.issue_id == issue_id)))
        activities = list(await db.scalars(select(Activity).where(Activity.repo_id == repository_id)))
        if failure is not None:
            assert comments == []
            assert activities == []
        else:
            assert len(comments) == len(activities) == 1
            assert str(comments[0].id) == response.json()["id"]
            assert activities[0].comment_id == comments[0].id


@pytest.mark.parametrize("fail", [False, True])
async def test_repository_deletion_and_fork_detachment_are_atomic(transaction_app: FastAPI, fail: bool) -> None:
    factory = transaction_app.state.db_session_factory
    repository_id, fork_id, issue_id = await _seed_repository(factory)
    async with AsyncClient(transport=ASGITransport(app=transaction_app), base_url="http://test") as client:
        response = await client.post("/repositories/admin/transactions/issues/1/comments", json={"body": "Reply"})
        assert response.status_code == 201
        response = await client.delete("/repositories/transactions", params={"fail": fail})

    assert response.status_code == (409 if fail else 200)
    async with factory() as db:
        assert (await db.get(Repository, repository_id) is not None) == fail
        assert (await db.get(Issue, issue_id) is not None) == fail
        fork = await db.get(Repository, fork_id)
        assert fork is not None
        assert fork.fork_of_id == (repository_id if fail else None)
        assert await db.scalar(select(func.count()).select_from(Comment).where(Comment.issue_id == issue_id)) == int(
            fail
        )
        assert await db.scalar(
            select(func.count()).select_from(Activity).where(Activity.repo_id == repository_id)
        ) == int(fail)
