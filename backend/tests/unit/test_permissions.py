"""Account and credential authorization are both defined by Casbin policy."""

from uuid import uuid4

import casbin
import pytest

from app.permissions import POLICY_DIRECTORY, owner_domain, policy_enforcer, repository_domain, scoped_enforcer


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
def test_policy_separates_roles_and_scopes(subject: str, operation: str, kind: str, *, allowed: bool) -> None:
    assert policy_enforcer().enforce(subject, operation, kind) == allowed


def test_casbin_policy_changes_control_both_limits_without_python_translation() -> None:
    enforcer = casbin.Enforcer(str(POLICY_DIRECTORY / "model.conf"), str(POLICY_DIRECTORY / "policy.csv"))
    enforcer.enable_auto_save(False)
    assert enforcer.enforce("read", "issues:write", "account")
    assert enforcer.enforce("issues:write", "issues:write", "token")
    enforcer.remove_policy("read", "issues:write", "token")
    enforcer.add_policy("write", "issues:write", "token")
    assert not enforcer.enforce("read", "issues:write", "account")
    assert enforcer.enforce("write", "issues:write", "account")
    enforcer.remove_policy("write", "issues:write", "token")
    enforcer.add_policy("write", "issues:write", "account")
    assert not enforcer.enforce("issues:write", "issues:write", "token")
    assert enforcer.enforce("owner", "issues:write", "account")


def test_relationships_inherit_inside_their_resource_and_organization_only() -> None:
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
    enforcer = scoped_enforcer(grants)
    assert enforcer.enforce("user:admin", parent, "organization:admin")
    assert enforcer.enforce("user:admin", resource, "repository:delete")
    assert enforcer.enforce("user:admin", sibling, "repository:delete")
    assert not enforcer.enforce("user:admin", foreign, "repository:read")
    assert enforcer.enforce("user:member", parent, "organization:read")
    assert not enforcer.enforce("user:member", parent, "organization:admin")
    assert not enforcer.enforce("user:member", resource, "repository:read")
    assert enforcer.enforce("user:writer", resource, "git:write")
    assert not enforcer.enforce("user:writer", sibling, "repository:read")
    assert not enforcer.enforce("user:writer", foreign, "repository:read")
    assert not enforcer.enforce("user:writer", parent, "organization:admin")
    assert not scoped_enforcer([]).enforce("user:writer", resource, "git:write")
    assert not any("user:" in value for rule in policy_enforcer().get_grouping_policy() for value in rule)
