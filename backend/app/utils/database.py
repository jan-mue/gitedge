from sqlalchemy.orm import Session

from app.clients.items import SQLItemRepository
from app.clients.users import SQLUserRepository
from app.config import settings
from app.schemas.users import UserCreate
from app.services.crud import CrudService


def init_db(session: Session) -> None:
    crud_service = CrudService(SQLUserRepository(session), SQLItemRepository(session))
    user = crud_service.get_user_by_email(email=settings.FIRST_SUPERUSER)
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = crud_service.create_user(user_create=user_in)
