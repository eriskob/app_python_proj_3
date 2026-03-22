from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from tasks.tasks import _cleanup_expired_links, cleanup_expired_links


@pytest.mark.asyncio
async def test_cleanup_expired_links_returns_deleted_rows_count():
    session = AsyncMock()
    session.execute.return_value.rowcount = 3

    session_cm = AsyncMock()
    session_cm.__aenter__.return_value = session
    session_cm.__aexit__.return_value = None

    with patch("tasks.tasks.async_session_maker", return_value=session_cm):
        deleted_rows = await _cleanup_expired_links()

    assert deleted_rows == 3
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()


def test_cleanup_expired_links_runs_async_cleanup():
    with patch("tasks.tasks.asyncio.run") as mocked_run, patch(
        "tasks.tasks._cleanup_expired_links", new=MagicMock(return_value="coroutine")
    ):
        cleanup_expired_links()

    mocked_run.assert_called_once()
