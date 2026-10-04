from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.sql import select

from app.backend_pre_start import init

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


async def test_init_successful_connection(mocker: MockerFixture) -> None:
    session_mock = mocker.AsyncMock()
    context_manager = mocker.MagicMock()
    context_manager.__aenter__ = mocker.AsyncMock(return_value=session_mock)
    context_manager.__aexit__ = mocker.AsyncMock(return_value=False)

    select1 = select(1)

    mocker.patch("app.backend_pre_start.get_db_session", return_value=context_manager)
    mocker.patch("app.backend_pre_start.select", return_value=select1)

    await init()

    session_mock.execute.assert_awaited_once_with(select1)
