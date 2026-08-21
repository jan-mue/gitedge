from typing import TYPE_CHECKING

from pydantic import EmailStr
from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.entities.base import Base

if TYPE_CHECKING:
    from app.entities.items import Item


class User(Base):
    __tablename__ = "user"

    email: Mapped[EmailStr] = mapped_column(String(255), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    items: Mapped[list[Item]] = relationship("Item", back_populates="owner", cascade="all, delete-orphan")
