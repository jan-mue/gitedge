"""Casbin evaluates account roles and token scopes against the same operations."""

from copy import deepcopy
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import casbin
from casbin import util

if TYPE_CHECKING:
    from uuid import UUID

type ScopeGrant = tuple[str, str, str]

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


@cache
def scoped_policy_model() -> casbin.Model:
    """Parse the scoped model once, keeping request-specific role graphs separate."""
    model = casbin.Model()
    model.load_model(str(POLICY_DIRECTORY / "scoped_model.conf"))
    return model


def scoped_enforcer(grants: list[ScopeGrant]) -> casbin.Enforcer:
    """Let Casbin inherit organization and team grants within UUID-based domains."""
    enforcer = casbin.Enforcer(deepcopy(scoped_policy_model()))
    enforcer.enable_auto_save(False)
    enforcer.enable_auto_build_role_links(False)
    enforcer.add_policies(policy_enforcer().get_policy())
    enforcer.add_named_domain_matching_func("g2", util.key_match2)
    hierarchy = [(child, parent, "*") for child, parent in policy_enforcer().get_grouping_policy()]
    enforcer.add_named_grouping_policies("g2", [list(grant) for grant in [*hierarchy, *grants]])
    enforcer.build_role_links()
    return enforcer


def owner_domain(owner_id: UUID) -> str:
    """Use immutable principal IDs to isolate namespaces."""
    return f"/owners/{owner_id}"


def repository_domain(owner_id: UUID, repository_id: UUID) -> str:
    """Nest a repository under its owner's namespace."""
    return f"{owner_domain(owner_id)}/repositories/{repository_id}"
