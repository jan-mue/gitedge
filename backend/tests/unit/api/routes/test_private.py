from __future__ import annotations

from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from app.services.crud import CrudService


def test_create_user(client: TestClient, crud: CrudService) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/private/users/",
        json={
            "email": "pollo@listo.com",
            "password": "password123",
            "full_name": "Pollo Listo",
        },
    )

    assert r.status_code == 200

    data = r.json()

    user = crud.get_user_by_id(data["id"])

    assert user
    assert user.email == "pollo@listo.com"
    assert user.full_name == "Pollo Listo"
