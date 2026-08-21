from unittest.mock import MagicMock, patch

from sqlalchemy.sql import select

from app.backend_pre_start import init


def test_init_successful_connection() -> None:
    session_mock = MagicMock()
    session_mock.__enter__.return_value = session_mock

    select1 = select(1)

    with (
        patch("app.backend_pre_start.get_db_session", return_value=session_mock),
        patch("app.backend_pre_start.select", return_value=select1),
    ):
        try:
            init()
            connection_successful = True
        except Exception:
            connection_successful = False

        assert connection_successful, "The database connection should be successful and not raise an exception."

        session_mock.execute.assert_called_once_with(select1)
