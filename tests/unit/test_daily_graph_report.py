"""Unit tests for daily_graph_report task (TASK-0060)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.settings import Settings


@pytest.fixture
def mock_settings() -> MagicMock:
    s = MagicMock(spec=Settings)
    s.admin_channel_id = -100123
    return s


@pytest.fixture
def mock_bot() -> AsyncMock:
    bot = AsyncMock()
    bot.send_photo = AsyncMock()
    return bot


@pytest.mark.asyncio
async def test_daily_graph_report_sends_photo_when_channel_set(
    mock_settings: MagicMock, mock_bot: AsyncMock
) -> None:
    from src.tasks.daily_graph_report import daily_graph_report

    with (
        patch("src.tasks.daily_graph_report.get_settings", return_value=mock_settings),
        patch("src.tasks.daily_graph_report.get_session") as mock_get,
        patch(
            "src.tasks.daily_graph_report.render_daily_charts",
            new=AsyncMock(return_value=b"\x89PNGfake"),
        ),
    ):
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        mock_get.return_value.__aenter__.return_value = mock_session

        ctx = {"bot": mock_bot}
        await daily_graph_report(ctx)

    mock_bot.send_photo.assert_awaited_once()
    args = mock_bot.send_photo.call_args
    assert args.kwargs["chat_id"] == -100123
    assert "photo" in args.kwargs


@pytest.mark.asyncio
async def test_daily_graph_report_noop_no_channel() -> None:
    from src.tasks.daily_graph_report import daily_graph_report

    s = MagicMock(spec=Settings)
    s.admin_channel_id = None
    with patch("src.tasks.daily_graph_report.get_settings", return_value=s):
        ctx = {"bot": AsyncMock()}
        await daily_graph_report(ctx)  # no crash, no send


@pytest.mark.asyncio
async def test_daily_graph_report_skip_no_bot(mock_settings: MagicMock) -> None:
    from src.tasks.daily_graph_report import daily_graph_report

    with patch("src.tasks.daily_graph_report.get_settings", return_value=mock_settings):
        ctx = {"bot": None}
        await daily_graph_report(ctx)  # no crash
