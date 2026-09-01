from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.sql import select

from app.backend_pre_start import init

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_init_successful_connection(mocker: MockerFixture) -> None:
    session_mock = mocker.MagicMock()
    session_mock.__enter__.return_value = session_mock

    select1 = select(1)

    mocker.patch("app.backend_pre_start.get_db_session", return_value=session_mock)
    mocker.patch("app.backend_pre_start.select", return_value=select1)

    init()

    session_mock.execute.assert_called_once_with(select1)
