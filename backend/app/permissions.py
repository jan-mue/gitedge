"""Casbin evaluates account roles and token scopes against the same operations."""

from functools import cache
from pathlib import Path
from typing import Literal

import casbin

POLICY_DIRECTORY = Path(__file__).resolve().parents[1] / "resources" / "authorization"
type SubjectKind = Literal["account", "token"]


@cache
def policy_enforcer() -> casbin.Enforcer:
    """Load deployment-static rules once; never add request-specific identity facts."""
    enforcer = casbin.Enforcer(str(POLICY_DIRECTORY / "model.conf"), str(POLICY_DIRECTORY / "policy.csv"))
    enforcer.enable_auto_save(False)
    return enforcer


@cache
def permitted_subjects(operation: str, kind: SubjectKind) -> frozenset[str]:
    """Compile Casbin's immutable grant relation, without caching an actor's access."""
    enforcer = policy_enforcer()
    subjects = set(enforcer.get_all_subjects()) | set(enforcer.get_all_actions())
    subjects.update(subject for relation in enforcer.get_grouping_policy() for subject in relation)
    return frozenset(subject for subject in subjects if enforcer.enforce(subject, operation, kind))


def permitted_roles(operation: str) -> frozenset[str]:
    """Find account roles allowed by Casbin for this operation."""
    return permitted_subjects(operation, "account")


def permitted_token_scopes(operation: str) -> frozenset[str]:
    """Find token scopes allowed by Casbin, including scope inheritance."""
    return permitted_subjects(operation, "token")
