from __future__ import annotations

from inspect import signature
from typing import TYPE_CHECKING

import pytest
from fastapi import HTTPException

from app.api.permissions import require_permission
from tests.unit.api.routes.test_authorization import add_repository, add_user, service

if TYPE_CHECKING:
    from tests.unit.utils.fakes import FakeStores


async def test_decorator_preserves_signature_and_checks_positional_arguments(fake_stores: FakeStores) -> None:
    owner = add_user(fake_stores, "owner")
    outsider = add_user(fake_stores, "outsider")
    add_repository(fake_stores, owner)
    calls = []

    async def route(owner: str, repo: str, _authorization: object, _current_user: object) -> str:
        calls.append((owner, repo))
        return repo

    before = signature(route, eval_str=True)
    decorated = require_permission("repository:write", authorization="_authorization", user="_current_user")(route)
    assert signature(decorated) == before
    assert getattr(decorated, "__name__", None) == "route"
    with pytest.raises(HTTPException) as denied:
        await decorated("owner", "repo", service(fake_stores), outsider)
    assert denied.value.status_code == 403
    assert calls == []
    assert await decorated("owner", "repo", service(fake_stores), owner) == "repo"
    assert calls == [("owner", "repo")]


def test_decorator_rejects_implicit_repository_parameters() -> None:
    async def route(repository: str) -> str:
        return repository

    with pytest.raises(TypeError, match="explicitly declare"):
        require_permission("repository:read")(route)
