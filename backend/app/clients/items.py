from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clients.database import CrudRepository, SQLRepository
from app.entities.items import Item


class ItemRepository(CrudRepository[Item], ABC):
    @abstractmethod
    def get_all_by_owner_id(self, owner_id: UUID | str, offset: int = 0, limit: int = 100) -> list[Item]:
        pass

    @abstractmethod
    def count_by_owner_id(self, owner_id: UUID | str) -> int:
        pass


class SQLItemRepository(ItemRepository, SQLRepository[Item]):
    def __init__(self, db: Session):
        super().__init__(db, Item)

    def get_all_by_owner_id(self, owner_id: UUID | str, offset: int = 0, limit: int = 100) -> list[Item]:
        query = select(Item).where(Item.owner_id == owner_id).offset(offset).limit(limit)
        return list(self.db.scalars(query).all())

    def count_by_owner_id(self, owner_id: UUID | str) -> int:
        query = select(func.count()).select_from(Item).where(Item.owner_id == owner_id)
        return self.db.execute(query).scalar_one()
