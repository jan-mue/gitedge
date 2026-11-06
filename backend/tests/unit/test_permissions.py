"""Account and credential authorization are both defined by Casbin policy."""

from uuid import uuid4

import pytest
from casbin import AsyncEnforcer

from app.permissions import Actor, Resource, owner_domain, policy_enforcer, repository_domain, scoped_enforcer


@pytest.mark.parametrize(
    ("subject", "operation", "kind", "allowed"),
    [
        ("owner", "repository:delete", "account", True),
        ("owner", "repository:delete", "token", False),
        ("repository:delete", "repository:delete", "token", True),
        ("repository:delete", "repository:delete", "account", False),
        ("git:write", "git:read", "token", True),
        ("git:read", "git:write", "token", False),
        ("repository:write", "git:write", "token", False),
        ("collaborators:write", "collaborators:write", "token", False),
        ("read", "issues:moderate", "account", False),
        ("write", "issues:moderate", "account", True),
        ("read", "comments:moderate", "account", False),
        ("admin", "pull_requests:moderate", "account", True),
    ],
)
async def test_policy_separates_roles_and_scopes(subject: str, operation: str, kind: str, *, allowed: bool) -> None:
    enforcer = await scoped_enforcer([("account", subject, "/repo")])
    actor = Actor("account") if kind == "account" else Actor(subject)
    assert enforcer.enforce(actor, Resource("/repo"), operation, kind) == allowed


async def test_casbin_policy_changes_control_both_limits_without_python_translation() -> None:
    enforcer = await scoped_enforcer([("reader", "read", "/repo"), ("writer", "write", "/repo")])
    assert isinstance(enforcer, AsyncEnforcer)
    resource = Resource("/repo")
    assert enforcer.enforce(Actor("reader"), resource, "issues:write", "account")
    assert enforcer.enforce(Actor("issues:write"), resource, "issues:write", "token")
    await enforcer.remove_policy("read", "issues:write", "token")
    await enforcer.add_policy("write", "issues:write", "token")
    assert not enforcer.enforce(Actor("reader"), resource, "issues:write", "account")
    assert enforcer.enforce(Actor("writer"), resource, "issues:write", "account")
    await enforcer.remove_policy("write", "issues:write", "token")
    await enforcer.add_policy("write", "issues:write", "account")
    assert not enforcer.enforce(Actor("issues:write"), resource, "issues:write", "token")


async def test_identity_and_visibility_attributes_are_evaluated_by_casbin() -> None:
    enforcer = await policy_enforcer()
    private = Resource("/repo", owner_subject="user:owner")
    public = Resource("/public", public=True)
    assert enforcer.enforce(Actor("user:owner"), private, "repository:delete", "account")
    assert enforcer.enforce(Actor("anonymous"), public, "repository:read", "account")
    assert not enforcer.enforce(Actor("anonymous"), public, "repository:write", "account")
    assert enforcer.enforce(Actor("user:admin", superuser=True), private, "repository:delete", "account")
    assert not enforcer.enforce(Actor("user:owner", active=False), private, "repository:read", "account")
    assert not enforcer.enforce(Actor("user:admin", active=False, superuser=True), public, "repository:read", "account")
    token = Resource("/tokens/1", owner_subject="user:owner")
    assert enforcer.enforce(Actor("user:owner"), token, "personal_tokens:manage", "account")
    assert not enforcer.enforce(Actor("user:admin", superuser=True), token, "personal_tokens:manage", "account")


async def test_relationships_inherit_inside_their_resource_and_organization_only() -> None:
    organization, sibling_organization, repository, sibling_repository = (uuid4() for _ in range(4))
    parent = owner_domain(organization)
    resource = repository_domain(organization, repository)
    sibling = repository_domain(organization, sibling_repository)
    foreign = repository_domain(sibling_organization, repository)
    grants = [
        ("user:admin", "org_admin", parent),
        ("user:admin", "org_admin", f"{parent}/*"),
        ("user:member", "org_member", parent),
        ("user:member", "org_member", f"{parent}/*"),
        ("user:writer", "team:engineering", f"{parent}/*"),
        ("team:engineering", "write", resource),
    ]
    enforcer = await scoped_enforcer(grants)
    assert enforcer.enforce(Actor("user:admin"), Resource(parent), "organization:admin", "account")
    assert enforcer.enforce(Actor("user:admin"), Resource(resource), "repository:delete", "account")
    assert enforcer.enforce(Actor("user:admin"), Resource(sibling), "repository:delete", "account")
    assert not enforcer.enforce(Actor("user:admin"), Resource(foreign), "repository:read", "account")
    assert enforcer.enforce(Actor("user:member"), Resource(parent), "organization:read", "account")
    assert not enforcer.enforce(Actor("user:member"), Resource(parent), "organization:admin", "account")
    assert not enforcer.enforce(Actor("user:member"), Resource(resource), "repository:read", "account")
    assert enforcer.enforce(Actor("user:writer"), Resource(resource), "git:write", "account")
    assert not enforcer.enforce(Actor("user:writer"), Resource(sibling), "repository:read", "account")
    assert not enforcer.enforce(Actor("user:writer"), Resource(foreign), "repository:read", "account")
    assert not enforcer.enforce(Actor("user:writer"), Resource(parent), "organization:admin", "account")
    assert not (await scoped_enforcer([])).enforce(Actor("user:writer"), Resource(resource), "git:write", "account")
    assert not any(
        "user:" in value for rule in (await policy_enforcer()).get_named_grouping_policy("g2") for value in rule
    )
