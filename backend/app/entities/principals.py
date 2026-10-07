"""Principal entity: the shared base for users and organizations."""

from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.entities.base import Base

if TYPE_CHECKING:
    from app.entities.repositories import Repository


class PrincipalType(StrEnum):
    """The kind of principal."""

    USER = "user"
    ORGANIZATION = "organization"


class Principal(Base):
    """A named owner (individual user or organization).

    Users and organizations share this table via joined-table inheritance, so
    a repository owner or activity actor is identified by a single id.
    """

    __tablename__ = "principal"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    lower_name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    principal_type: Mapped[PrincipalType] = mapped_column("type", String(20), nullable=False)

    repositories: Mapped[list["Repository"]] = relationship(back_populates="owner")

    __mapper_args__ = {"polymorphic_on": principal_type, "polymorphic_identity": "principal"}
