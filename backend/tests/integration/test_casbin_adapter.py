"""Adapter persistence, transactional revocation, and migration of existing relationships."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from psycopg import sql
from pydantic import PostgresDsn
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import Session

from app.clients.authorization import SQLAuthorizationStore
from app.clients.casbin import RelationshipAdapter
from app.clients.database import create_session_factory
from app.clients.repositories import SQLRepositoryStore
from app.config import settings
from app.constants import BACKEND_DIR
from app.entities.authorization import OrganizationMember, RepositoryCollaborator, Team, TeamMember
from app.entities.casbin import CasbinRule
from app.entities.organizations import Organization
from app.entities.repositories import Repository
from app.entities.users import User
from app.permissions import owner_domain, repository_domain, scoped_enforcer
from tests.conftest import _run_async

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_adapter_migration_and_transactions(infrastructure: dict[str, str], mocker: MockerFixture) -> None:
    """Upgrade existing grants, then reject a partial metadata/policy update without losing access."""
    source_url = make_url(infrastructure["DATABASE_URL"])
    database_name = f"casbin_migration_{uuid.uuid4().hex}"
    control_url = source_url.set(drivername="postgresql", database="postgres").render_as_string(hide_password=False)
    database_url = source_url.set(database=database_name).render_as_string(hide_password=False)
    with psycopg.connect(control_url, autocommit=True) as control:
        control.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    engine = create_engine(database_url)
    try:
        mocker.patch.object(settings, "DATABASE_URL", PostgresDsn(database_url))
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
        command.upgrade(config, "05b106a4cc76")
        with Session(engine) as db:
            user = User(
                name="adapter-user",
                lower_name="adapter-user",
                email="adapter@example.com",
                hashed_password="unused",
                is_active=True,
            )
            organization = Organization(name="adapter-org", lower_name="adapter-org")
            db.add_all([user, organization])
            db.flush()
            team = Team(organization_id=organization.id, name="engineering")
            repository = Repository(name="project", owner_id=organization.id, is_private=True)
            db.add_all([team, repository])
            db.flush()
            grant = RepositoryCollaborator(repository_id=repository.id, team_id=team.id, role="write")
            db.add_all(
                [
                    OrganizationMember(organization_id=organization.id, user_id=user.id, is_admin=False),
                    TeamMember(team_id=team.id, user_id=user.id),
                    grant,
                    RepositoryCollaborator(repository_id=repository.id, user_id=user.id, role="read"),
                ]
            )
            db.commit()
            user_id, organization_id, repository_id, team_id, grant_id = (
                user.id,
                organization.id,
                repository.id,
                team.id,
                grant.id,
            )
        expected = {
            (f"user:{user_id}", "org_member", owner_domain(organization_id)),
            (f"user:{user_id}", "org_member", f"{owner_domain(organization_id)}/*"),
            (f"user:{user_id}", f"team:{team_id}", f"{owner_domain(organization_id)}/*"),
            (f"team:{team_id}", "write", repository_domain(organization_id, repository_id)),
            (f"user:{user_id}", "read", repository_domain(organization_id, repository_id)),
        }
        for cycle in range(2):
            command.upgrade(config, "head")
            command.check(config)
            with Session(engine) as db:
                assert set(db.execute(select(CasbinRule.v0, CasbinRule.v1, CasbinRule.v2))) == expected
            _run_async(check_adapter_transaction(database_url, user_id, repository_id, grant_id, mocker))
            if cycle == 0:
                command.downgrade(config, "05b106a4cc76")
    finally:
        engine.dispose()
        with psycopg.connect(control_url, autocommit=True) as control:
            control.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name)))


async def check_adapter_transaction(
    database_url: str, user_id: uuid.UUID, repository_id: uuid.UUID, grant_id: uuid.UUID, mocker: MockerFixture
) -> None:
    engine = create_async_engine(database_url)
    try:
        async with create_session_factory(engine)() as db:
            facts = SQLAuthorizationStore(db)
            repository = await SQLRepositoryStore(db).get(repository_id)
            domain = repository_domain(repository.owner_id, repository.id)
            grant = await db.get(RepositoryCollaborator, grant_id)
            assert grant is not None
            failure = mocker.patch.object(
                RelationshipAdapter, "add_policy", side_effect=RuntimeError("policy write failed")
            )
            transaction = await db.begin_nested()
            try:
                grant.role = "admin"
                with pytest.raises(RuntimeError, match="policy write failed"):
                    await facts.save(grant)
            finally:
                if transaction.is_active:
                    await transaction.rollback()
                mocker.stop(failure)
            await db.refresh(grant)
            assert grant.role == "write"
            relationships = await facts.scope_grants(user_id, [repository])
            enforcer = scoped_enforcer(relationships)
            assert enforcer.enforce(f"user:{user_id}", domain, "git:write")
            assert not enforcer.enforce(f"user:{user_id}", domain, "repository:write")
    finally:
        await engine.dispose()
