"""Private API routes for testing purposes only.

These endpoints should not be exposed in production.
"""

from fastapi import APIRouter

from app.api.dependencies import UserStoreDep
from app.entities.users import User
from app.schemas.base import GitEdgeBaseModel
from app.schemas.users import UserPublic
from app.utils.security import get_password_hash

router = APIRouter(tags=["private"], prefix="/private")


class PrivateUserCreate(GitEdgeBaseModel):
    """Schema for creating a user via private API."""

    email: str
    password: str
    full_name: str
    is_verified: bool = False


@router.post("/users/", response_model=UserPublic)
async def create_user(user_in: PrivateUserCreate, user_store: UserStoreDep) -> UserPublic:
    """Create a new user.

    This endpoint is intended for testing purposes only.

    Args:
        user_in: User creation data.
        user_store: User store dependency.

    Returns:
        The created user public data.
    """
    user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
    )

    await user_store.add(user)

    return UserPublic.model_validate(user)
