from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from app.services.crud import CrudService


async def test_create_user(client: TestClient, crud: CrudService) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/private/users/",
        json={
            "email": "pollo@listo.com",
            "password": "password123",
            "display_name": "Pollo Listo",
        },
    )

    assert r.status_code == 200

    data = r.json()

    user = await crud.get_user_by_id(uuid.UUID(data["id"]))

    assert user
    assert user.email == "pollo@listo.com"
    assert user.display_name == "Pollo Listo"
