from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.sql import select

from app.backend_pre_start import init

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


async def test_init_successful_connection(mocker: MockerFixture) -> None:
    session_mock = mocker.AsyncMock()
    session_context = mocker.MagicMock()
    session_context.__aenter__ = mocker.AsyncMock(return_value=session_mock)
    session_context.__aexit__ = mocker.AsyncMock(return_value=False)

    session_factory = mocker.MagicMock(return_value=session_context)

    engine_mock = mocker.AsyncMock()

    select1 = select(1)

    mocker.patch("app.clients.database.create_async_engine", return_value=engine_mock)
    mocker.patch("app.backend_pre_start.create_session_factory", return_value=session_factory)
    mocker.patch("app.backend_pre_start.select", return_value=select1)

    await init()

    session_mock.execute.assert_awaited_once_with(select1)
    engine_mock.dispose.assert_awaited_once()
