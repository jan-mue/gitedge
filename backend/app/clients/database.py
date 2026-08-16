import uuid
from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.entities.base import Base

engine: Engine | None = None


# TODO: use async session
def get_db_session() -> Session:
    global engine  # noqa: PLW0603
    if engine is None:
        engine = create_engine(
            url=str(settings.DATABASE_URL),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return Session(autocommit=False, autoflush=False, bind=engine)


class CrudRepository[T: Base](ABC):
    @abstractmethod
    def get(self, primary_key: uuid.UUID | str) -> T | None:
        pass

    @abstractmethod
    def get_all(self, offset: int = 0, limit: int = 100) -> list[T]:
        pass

    @abstractmethod
    def count(self) -> int:
        pass

    @abstractmethod
    def add(self, obj: T) -> None:
        pass

    @abstractmethod
    def update(self, obj: T, new_data: dict[str, Any] | None = None) -> None:
        pass

    @abstractmethod
    def delete(self, obj: T) -> None:
        pass

    @abstractmethod
    def refresh(self, obj: T) -> None:
        pass


class SQLRepository[T: Base](CrudRepository[T]):
    def __init__(self, db: Session, entity_class: type[T]):
        self.db = db
        self.entity_class = entity_class

    def get(self, primary_key: uuid.UUID | str) -> T | None:
        return self.db.scalar(
            select(self.entity_class).where(self.entity_class.id == primary_key)
        )

    def get_all(self, offset: int = 0, limit: int = 100) -> list[T]:
        return list(
            self.db.scalars(
                select(self.entity_class)
                .order_by(self.entity_class.created_at.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )

    def count(self) -> int:
        return self.db.execute(
            select(func.count()).select_from(self.entity_class)
        ).scalar_one()

    def add(self, obj: T) -> None:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)

    def update(self, obj: T, new_data: dict[str, Any] | None = None) -> None:
        if new_data:
            for key, value in new_data.items():
                setattr(obj, key, value)
        self.db.commit()

    def delete(self, obj: T) -> None:
        self.db.delete(obj)
        self.db.commit()

    def refresh(self, obj: T) -> None:
        self.db.refresh(obj)
