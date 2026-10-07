"""Organization entity model."""

import uuid

from sqlalchemy import UUID, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.entities.principals import Principal, PrincipalType


class Organization(Principal):
    """Organization database model - extends Principal (joined table inheritance)."""

    __tablename__ = "organization"
    __mapper_args__ = {"polymorphic_identity": PrincipalType.ORGANIZATION}

    # Use the same id as Principal (foreign key to Principal primary key) - override parent
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("principal.id"),
        primary_key=True,
    )

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
