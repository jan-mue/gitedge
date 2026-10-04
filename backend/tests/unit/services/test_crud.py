from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.encoders import jsonable_encoder

from app.schemas.users import UserCreate, UserUpdate
from app.utils.security import verify_password
from tests.unit.utils.utils import random_email, random_lower_string

if TYPE_CHECKING:
    from app.services.crud import CrudService


async def test_create_user(crud: CrudService) -> None:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password)
    user = await crud.create_user(user_create=user_in)
    assert user.email == email


async def test_authenticate_user(crud: CrudService) -> None:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password)
    user = await crud.create_user(user_create=user_in)
    authenticated_user = await crud.authenticate(email=email, password=password)
    assert authenticated_user
    assert user.email == authenticated_user.email


async def test_not_authenticate_user(crud: CrudService) -> None:
    email = random_email()
    password = random_lower_string()
    user = await crud.authenticate(email=email, password=password)
    assert user is None


async def test_check_if_user_is_active(crud: CrudService) -> None:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password)
    user = await crud.create_user(user_create=user_in)
    assert user.is_active is True


async def test_check_if_user_is_active_inactive(crud: CrudService) -> None:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password, is_active=False)
    user = await crud.create_user(user_create=user_in)
    assert user.is_active is False


async def test_check_if_user_is_superuser(crud: CrudService) -> None:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password, is_superuser=True)
    user = await crud.create_user(user_create=user_in)
    assert user.is_superuser is True


async def test_check_if_user_is_superuser_normal_user(crud: CrudService) -> None:
    username = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=username, password=password)
    user = await crud.create_user(user_create=user_in)
    assert user.is_superuser is False


async def test_get_user(crud: CrudService) -> None:
    password = random_lower_string()
    username = random_email()
    user_in = UserCreate(email=username, password=password, is_superuser=True)
    user = await crud.create_user(user_create=user_in)
    user_2 = await crud.get_user_by_id(user.id)
    assert user_2
    assert user.email == user_2.email
    assert jsonable_encoder(user) == jsonable_encoder(user_2)


async def test_update_user(crud: CrudService) -> None:
    password = random_lower_string()
    email = random_email()
    user_in = UserCreate(email=email, password=password, is_superuser=True)
    user = await crud.create_user(user_create=user_in)
    new_password = random_lower_string()
    user_in_update = UserUpdate(password=new_password, is_superuser=True)
    if user.id is not None:
        db_user = await crud.user_store.get(user.id)
        assert db_user is not None
        await crud.update_user(db_user=db_user, user_in=user_in_update)
    user_2 = await crud.user_store.get(user.id)
    assert user_2
    assert user.email == user_2.email
    verified, _ = verify_password(new_password, user_2.hashed_password)
    assert verified
