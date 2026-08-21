from fastapi import APIRouter
from pydantic import BaseModel

from app.api.dependencies import UserRepositoryDep
from app.entities.users import User
from app.schemas.users import UserPublic
from app.utils.security import get_password_hash

router = APIRouter(tags=["private"], prefix="/private")


class PrivateUserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    is_verified: bool = False


@router.post("/users/", response_model=UserPublic)
def create_user(user_in: PrivateUserCreate, user_repository: UserRepositoryDep) -> UserPublic:
    """
    Create a new user.
    """

    user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
    )

    user_repository.add(user)

    return UserPublic.model_validate(user)
