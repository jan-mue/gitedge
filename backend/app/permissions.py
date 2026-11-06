"""One AsyncEnforcer model for account relationships and restricted token credentials."""

from copy import deepcopy
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

import casbin
from casbin import util
from casbin.persist.adapters import FileAdapter

from app.schemas.authorization import Actor, Resource

if TYPE_CHECKING:
    from uuid import UUID

    from casbin.persist.adapters.asyncio import AsyncAdapter

    from app.entities.users import User

POLICY_DIRECTORY = Path(__file__).resolve().parents[1] / "resources" / "authorization"
type ScopeGrant = tuple[str, str, str]


@cache
def policy_model() -> casbin.Model:
    """Parse immutable deployment policy once; never cache an actor or decision."""
    model = casbin.Model()
    model.load_model(str(POLICY_DIRECTORY / "model.conf"))
    FileAdapter(str(POLICY_DIRECTORY / "policy.csv")).load_policy(model)
    return model


async def policy_enforcer(adapter: AsyncAdapter | None = None, policy_filter: object = None) -> casbin.AsyncEnforcer:
    """Load current adapter relationships and evaluate them with the sole authorization model."""
    model = policy_model()
    enforcer = casbin.AsyncEnforcer(deepcopy(model), adapter)
    enforcer.enable_auto_save(False)
    enforcer.enable_auto_build_role_links(False)
    if adapter is not None:
        await enforcer.load_filtered_policy(policy_filter)
    await enforcer.add_policies(model.get_policy("p", "p"))
    hierarchy = model.get_policy("g", "g")
    await enforcer.add_named_grouping_policies("g", hierarchy)
    await enforcer.add_named_grouping_policies("g2", [[child, parent, "*"] for child, parent in hierarchy])
    enforcer.add_named_domain_matching_func("g2", util.key_match2)
    enforcer.build_role_links()
    enforcer.enable_auto_build_role_links(True)
    enforcer.enable_auto_save(adapter is not None)
    return enforcer


async def scoped_enforcer(grants: list[ScopeGrant]) -> casbin.AsyncEnforcer:
    """Build the same AsyncEnforcer with an in-memory adapter's relationships in tests."""
    enforcer = await policy_enforcer()
    await enforcer.add_named_grouping_policies("g2", [list(grant) for grant in dict.fromkeys(grants)])
    return enforcer


async def permitted_roles(operation: str, actor: Actor | None = None) -> frozenset[str]:
    """Project Casbin decisions into indexed SQL listing/count predicates, never another policy."""
    actor = actor or Actor("query")
    model = policy_model()
    candidates = {row[0] for row in model.get_policy("p", "p")}
    candidates.update(value for row in model.get_policy("g", "g") for value in row)
    enforcer = await scoped_enforcer([(actor.name, role, role) for role in candidates])
    return frozenset(role for role in candidates if enforcer.enforce(actor, Resource(role), operation, "account"))


def owner_domain(owner_id: UUID) -> str:
    """Use immutable principal IDs to isolate namespaces."""
    return f"/owners/{owner_id}"


def repository_domain(owner_id: UUID, repository_id: UUID) -> str:
    """Nest a repository under its owner's namespace."""
    return f"{owner_domain(owner_id)}/repositories/{repository_id}"


@dataclass(frozen=True)
class RepositoryVisibility:
    """SQL query inputs compiled exclusively from AsyncEnforcer decisions."""

    user_id: UUID | None
    unrestricted: bool
    public_read: bool
    owned_read: bool
    roles: frozenset[str]


async def repository_visibility(user: User | None) -> RepositoryVisibility:
    """Compile the model's resource decisions for scalable listing and count queries."""
    actor = (
        Actor(f"user:{user.id}", active=bool(user.is_active), superuser=bool(user.is_superuser))
        if user
        else Actor("anonymous")
    )
    enforcer = await policy_enforcer()
    return RepositoryVisibility(
        user.id if user else None,
        enforcer.enforce(actor, Resource("/query"), "repository:read", "account"),
        enforcer.enforce(actor, Resource("/query", public=True), "repository:read", "account"),
        enforcer.enforce(
            actor,
            Resource("/query", owner_subject=f"user:{user.id}" if user else "no-owner"),
            "repository:read",
            "account",
        ),
        await permitted_roles("repository:read", actor),
    )


async def account_can(user: User, operation: str) -> bool:
    """Evaluate site administration using the same AsyncEnforcer."""
    enforcer = await policy_enforcer()
    return enforcer.enforce(
        Actor(f"user:{user.id}", bool(user.is_active), bool(user.is_superuser)),
        Resource("/account"),
        operation,
        "account",
    )
