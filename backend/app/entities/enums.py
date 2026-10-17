"""SQLAlchemy enum columns that persist the public string values."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from enum import StrEnum

from sqlalchemy import Enum


def string_enum(enum: type[StrEnum], length: int | None = None) -> Enum:
    """Use portable enum columns and return enum members when loading models."""
    return Enum(
        enum,
        values_callable=lambda members: [member.value for member in members],
        native_enum=False,
        validate_strings=True,
        length=length,
    )
