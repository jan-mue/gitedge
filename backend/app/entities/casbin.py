"""Adapter-owned policy records registered with the application's Alembic metadata."""

from casbin_async_sqlalchemy_adapter import create_casbin_rule_model
from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase

from app.entities.base import Base


class PolicyBase(DeclarativeBase):
    """Share metadata while retaining the adapter's integer primary-key convention."""

    metadata = Base.metadata


CasbinRule = create_casbin_rule_model(PolicyBase)
CasbinRule.__table__.append_constraint(UniqueConstraint("ptype", "v0", "v1", "v2", name="casbin_rule_relationship_key"))
Index("casbin_rule_subject_domain_idx", CasbinRule.ptype, CasbinRule.v0, CasbinRule.v2)
Index("casbin_rule_domain_subject_idx", CasbinRule.ptype, CasbinRule.v2, CasbinRule.v0)
