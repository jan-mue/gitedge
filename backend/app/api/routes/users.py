"""User management routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    CrudServiceDep,
    CurrentUser,
    EmailClientDep,
    SessionDep,
    UserStoreDep,
    get_current_active_superuser,
)
from app.config import settings
from app.schemas.users import (
    UpdatePassword,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)
from app.utils.email import generate_new_account_email
from app.utils.security import get_password_hash, verify_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", dependencies=[Depends(get_current_active_superuser)])
async def read_users(user_store: UserStoreDep, skip: int = 0, limit: int = 100) -> UsersPublic:
    """Retrieve users."""
    count = user_store.count()
    users = user_store.get_all(offset=skip, limit=limit)

    return UsersPublic(data=[UserPublic.model_validate(user) for user in users], count=count)


@router.post("/", dependencies=[Depends(get_current_active_superuser)])
async def create_user(*, crud_service: CrudServiceDep, user_in: UserCreate, email_client: EmailClientDep) -> UserPublic:
    """Create new user."""
    user = crud_service.get_user_by_email(email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    user = crud_service.create_user(user_create=user_in)
    if settings.emails_enabled and user_in.email:
        email_data = generate_new_account_email(
            email_to=user_in.email, username=user_in.email, password=user_in.password
        )
        email_client.send_email(
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return user


@router.patch("/me")
async def update_user_me(
    *, crud_service: CrudServiceDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> UserPublic:
    """Update own user."""
    if user_in.email:
        existing_user = crud_service.get_user_by_email(email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(status_code=409, detail="User with this email already exists")
    return crud_service.update_user(db_user=current_user, user_in=user_in)


@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def update_password_me(*, user_store: UserStoreDep, body: UpdatePassword, current_user: CurrentUser) -> None:
    """Update own password."""
    verified, _ = verify_password(body.current_password, current_user.hashed_password)
    if not verified:
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(status_code=400, detail="New password cannot be the same as the current one")
    hashed_password = get_password_hash(body.new_password)
    current_user.hashed_password = hashed_password
    user_store.update(current_user)


@router.get("/me")
async def read_user_me(current_user: CurrentUser) -> UserPublic:
    """Get current user."""
    return UserPublic.model_validate(current_user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_me(session: SessionDep, current_user: CurrentUser) -> None:
    """Delete own user."""
    if current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Super users are not allowed to delete themselves")
    # TODO: delete repositories
    # TODO: move to service
    session.delete(current_user)
    session.commit()


@router.post("/signup")
async def register_user(crud_service: CrudServiceDep, user_in: UserRegister) -> UserPublic:
    """Create new user without the need to be logged in."""
    user = crud_service.get_user_by_email(email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )
    user_create = UserCreate.model_validate(user_in)
    return crud_service.create_user(user_create=user_create)


@router.get("/{user_id}")
async def read_user_by_id(user_id: uuid.UUID, user_store: UserStoreDep, current_user: CurrentUser) -> UserPublic:
    """Get a specific user by id."""
    user = user_store.get(user_id)
    if user != current_user and not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserPublic.model_validate(user)


@router.patch("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
async def update_user(
    *, user_store: UserStoreDep, crud_service: CrudServiceDep, user_id: uuid.UUID, user_in: UserUpdate
) -> UserPublic:
    """Update a user."""
    db_user = user_store.get(user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    if user_in.email:
        existing_user = crud_service.get_user_by_email(email=user_in.email)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(status_code=409, detail="User with this email already exists")

    return crud_service.update_user(db_user=db_user, user_in=user_in)


@router.delete(
    "/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(get_current_active_superuser)]
)
async def delete_user(
    session: SessionDep, user_store: UserStoreDep, current_user: CurrentUser, user_id: uuid.UUID
) -> None:
    """Delete a user."""
    # TODO: move to service
    user = user_store.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user == current_user:
        raise HTTPException(status_code=403, detail="Super users are not allowed to delete themselves")
    # TODO: delete repositories
    session.delete(user)
    session.commit()
