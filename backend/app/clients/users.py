from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.database import CrudRepository, SQLRepository
from app.entities.users import User


class UserRepository(CrudRepository[User], ABC):
    @abstractmethod
    def get_by_email(self, email: str) -> User | None:
        pass


class SQLUserRepository(UserRepository, SQLRepository[User]):
    def __init__(self, db: Session):
        super().__init__(db, User)

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))
