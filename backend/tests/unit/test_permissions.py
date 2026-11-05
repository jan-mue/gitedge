"""Account and credential authorization are both defined by Casbin policy."""

import casbin
import pytest

from app.permissions import POLICY_DIRECTORY, policy_enforcer


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
