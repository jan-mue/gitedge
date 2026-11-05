"""Official async adapter bound to the request's database transaction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from casbin_async_sqlalchemy_adapter import Adapter
from sqlalchemy import or_, select
from sqlalchemy.orm import aliased

from app.entities.casbin import CasbinRule

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.selectable import Select


@dataclass(frozen=True)
class RelationshipFilter:
    """Bound loading to one actor, their teams, and the requested resource domains."""

    subject: str
    domains: list[str]


class RelationshipAdapter(Adapter):
    """Use the official persistence implementation with a SQL-scoped relationship filter."""

    def __init__(self, db: AsyncSession) -> None:
        """Join the application's transaction; never create tables or a separate engine."""
        super().__init__(db.bind, db_class=CasbinRule, db_session=db)

    @override
    def filter_query(self, stmt: Select[tuple[object]], filter: RelationshipFilter) -> Select[tuple[object]]:
        """Fetch the actor's relationship closure in one query without loading a whole tenant."""
        membership = aliased(CasbinRule)
        teams = select(CasbinRule.v1).where(
            CasbinRule.ptype == "g2",
            CasbinRule.v0 == filter.subject,
            CasbinRule.v1.startswith("team:"),
            CasbinRule.v2.in_(filter.domains),
            select(membership.id)
            .where(
                membership.ptype == "g2",
                membership.v0 == filter.subject,
                membership.v1.in_(["org_admin", "org_member"]),
                membership.v2 == CasbinRule.v2,
            )
            .exists(),
        )
        return stmt.where(
            CasbinRule.ptype == "g2",
            CasbinRule.v2.in_(filter.domains),
            or_(CasbinRule.v0 == filter.subject, CasbinRule.v0.in_(teams)),
        ).order_by(CasbinRule.id)
