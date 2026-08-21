from fastapi.testclient import TestClient

from app.config import settings
from app.schemas.users import UserCreate, UserPublic, UserUpdate
from app.services.crud import CrudService
from tests.utils.utils import random_email, random_lower_string


def user_authentication_headers(*, client: TestClient, email: str, password: str) -> dict[str, str]:
    data = {"username": email, "password": password}

    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=data)
    response = r.json()
    auth_token = response["access_token"]
    headers = {"Authorization": f"Bearer {auth_token}"}
    return headers


def create_random_user(crud: CrudService) -> UserPublic:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password)
    user = crud.create_user(user_create=user_in)
    return user


def authentication_token_from_email(*, client: TestClient, email: str, crud: CrudService) -> dict[str, str]:
    """
    Return a valid token for the user with given email.

    If the user doesn't exist it is created first.
    """
    password = random_lower_string()
    user = crud.user_repository.get_by_email(email=email)
    if not user:
        user_in_create = UserCreate(email=email, password=password)
        crud.create_user(user_create=user_in_create)
    else:
        user_in_update = UserUpdate(password=password)
        if not user.id:
            raise Exception("User id not set")
        crud.update_user(db_user=user, user_in=user_in_update)

    return user_authentication_headers(client=client, email=email, password=password)
