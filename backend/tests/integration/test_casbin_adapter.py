"""Casbin is the sole grant store and failed policy mutations roll back atomically."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app.clients.authorization import SQLAuthorizationStore
from app.clients.casbin import RelationshipAdapter
from app.clients.database import create_session_factory
from app.clients.repositories import SQLRepositoryStore
from app.clients.users import SQLUserStore
from app.entities.organizations import Organization
from app.entities.repositories import Repository
from app.entities.users import User
from app.permissions import Actor, Resource, owner_domain, repository_domain
from app.schemas.authorization import RepositoryCollaborator
from tests.conftest import _run_async

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_casbin_only_schema_and_transactions(infrastructure: dict[str, str], mocker: MockerFixture) -> None:
    url = infrastructure["DATABASE_URL"]
    engine = create_engine(url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert "casbin_rule" in tables
        assert not tables & {"organization_member", "repository_collaborator", "team_member"}
    finally:
        engine.dispose()
    _run_async(check_policy_transaction(url, mocker))


async def check_policy_transaction(url: str, mocker: MockerFixture) -> None:
    engine = create_async_engine(url)
    try:
        async with create_session_factory(engine)() as db:
            suffix = uuid.uuid4().hex
            users = SQLUserStore(db)
            repositories = SQLRepositoryStore(db)
            policies = SQLAuthorizationStore(db)
            user = User(
                name=f"policy-{suffix}",
                lower_name=f"policy-{suffix}",
                email=f"{suffix}@example.com",
                hashed_password="unused",
                is_active=True,
            )
            await users.add(user)
            organization = Organization(name=f"policy-org-{suffix}", lower_name=f"policy-org-{suffix}")
            await policies.create_organization(organization, user.id)
            repository = Repository(name="private", owner_id=organization.id, is_private=True)
            await repositories.add(repository)
            # A direct grant lets us test replacement without metadata tables.
            grant = RepositoryCollaborator(repository_id=repository.id, user_id=user.id, role="read")
            await policies.save(grant)
            before = await policies.collaborators(repository.id)
            assert len(before) == 1
            assert before[0].role == "read"
            failure = mocker.patch.object(
                RelationshipAdapter, "add_policy", side_effect=RuntimeError("policy write failed")
            )
            transaction = await db.begin_nested()
            try:
                grant.role = "admin"
                with pytest.raises(RuntimeError, match="policy write failed"):
                    await policies.save(grant)
            finally:
                if transaction.is_active:
                    await transaction.rollback()
                mocker.stop(failure)
            after = await policies.collaborators(repository.id)
            assert len(after) == 1
            assert after[0].role == "read"
            enforcer = await policies.enforcer(
                user.id, [owner_domain(organization.id), repository_domain(organization.id, repository.id)]
            )
            assert enforcer.enforce(
                Actor(f"user:{user.id}"), Resource(owner_domain(organization.id)), "organization:admin", "account"
            )
            await repositories.delete(repository)
            assert not await policies.collaborators(repository.id)
    finally:
        await engine.dispose()
