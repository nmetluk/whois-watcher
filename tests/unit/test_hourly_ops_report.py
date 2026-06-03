"""Unit-тесты ARQ-задачи hourly_ops_report (TASK-0059, ADR 042).

Моки: DB session (SQL counts), redis (ops:last_backup), AlertService (со spec),
ctx. Покрыты happy, backup-failed, no-channel, missing ctx.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.limits import Limits
from src.config.settings import Settings
from src.services.alerts import AlertService


@pytest.fixture
def mock_settings() -> Settings:
    """Settings с admin_channel_id."""
    s = MagicMock(spec=Settings)
    s.admin_channel_id = -1001234567890
    return s


@pytest.fixture
def mock_limits() -> Limits:
    return MagicMock(spec=Limits)


@pytest.fixture
def mock_bot() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_redis() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_alerts(
    mock_bot: AsyncMock, mock_redis: AsyncMock, mock_settings: Settings, mock_limits: Limits
) -> MagicMock:
    """AlertService со spec для проверок вызова send_ops."""
    a = MagicMock(spec=AlertService)
    a.send_ops = AsyncMock()
    return a


def _ctx(*, bot: AsyncMock, redis: AsyncMock, settings: Settings | None = None) -> dict:
    return {
        "bot": bot,
        "sync_redis": redis,
        "redis": redis,
        "settings": settings,
    }


class TestHourlyOpsReport:
    @pytest.mark.asyncio
    async def test_happy_path_with_backup_ok_sends_ops(
        self,
        mock_bot: AsyncMock,
        mock_redis: AsyncMock,
        mock_settings: Settings,
        mock_limits: Limits,
        mock_alerts: MagicMock,
    ) -> None:
        from src.tasks.hourly_ops_report import hourly_ops_report

        # Настраиваем redis.get для backup status
        mock_redis.get.return_value = '{"ok": true, "size": 123456, "path": "/backups/ww-xxx.dump"}'

        # Мокаем AlertService
        with (
            patch("src.tasks.hourly_ops_report.AlertService", return_value=mock_alerts),
            patch("src.tasks.hourly_ops_report.get_settings", return_value=mock_settings),
            patch("src.tasks.hourly_ops_report.get_limits", return_value=mock_limits),
        ):
            # Мокаем сессию и SQL-результаты
            mock_session = AsyncMock()
            # Порядок execute в _collect: active, new_doms, lookups, sys_err, aud_err
            scalars = [
                42,
                7,
                123,
                2,
                1,
            ]  # active, new, lookups, sys_err, aud_err -> errors=3

            async def fake_execute(sql):
                res = MagicMock()
                res.scalar_one.return_value = scalars.pop(0)
                return res

            mock_session.execute = fake_execute

            with patch("src.tasks.hourly_ops_report.get_session") as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = mock_session

                ctx = _ctx(bot=mock_bot, redis=mock_redis, settings=mock_settings)
                await hourly_ops_report(ctx)

        mock_alerts.send_ops.assert_awaited_once()
        text = mock_alerts.send_ops.call_args[0][0]
        assert "users 42" in text
        assert "lookups 123" in text
        assert "+домены 7" in text
        assert "ошибки 3" in text
        assert "💾 бекап ✅ 123456" in text

    @pytest.mark.asyncio
    async def test_backup_failed_reports_error(
        self,
        mock_bot: AsyncMock,
        mock_redis: AsyncMock,
        mock_settings: Settings,
        mock_limits: Limits,
        mock_alerts: MagicMock,
    ) -> None:
        from src.tasks.hourly_ops_report import hourly_ops_report

        mock_redis.get.return_value = '{"ok": false, "error": "pg_restore failed", "size": 0}'

        with (
            patch("src.tasks.hourly_ops_report.AlertService", return_value=mock_alerts),
            patch("src.tasks.hourly_ops_report.get_settings", return_value=mock_settings),
            patch("src.tasks.hourly_ops_report.get_limits", return_value=mock_limits),
        ):
            mock_session = AsyncMock()

            async def fake_execute(sql):
                res = MagicMock()
                res.scalar_one.return_value = 0
                return res

            mock_session.execute = fake_execute

            with patch("src.tasks.hourly_ops_report.get_session") as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = mock_session

                ctx = _ctx(bot=mock_bot, redis=mock_redis, settings=mock_settings)
                await hourly_ops_report(ctx)

        text = mock_alerts.send_ops.call_args[0][0]
        assert "бекап ❌ pg_restore failed" in text

    @pytest.mark.asyncio
    async def test_no_admin_channel_skips(
        self, mock_bot: AsyncMock, mock_redis: AsyncMock, mock_limits: Limits
    ) -> None:
        from src.tasks.hourly_ops_report import hourly_ops_report

        s = MagicMock(spec=Settings)
        s.admin_channel_id = None

        with patch("src.tasks.hourly_ops_report.get_settings", return_value=s):
            ctx = _ctx(bot=mock_bot, redis=mock_redis, settings=s)
            # Не должно упасть и не звать send
            await hourly_ops_report(ctx)

    @pytest.mark.asyncio
    async def test_missing_bot_or_redis_skips_and_warns(
        self, mock_settings: Settings, mock_limits: Limits, caplog: pytest.LogCaptureFixture
    ) -> None:
        from src.tasks.hourly_ops_report import hourly_ops_report

        with (
            patch("src.tasks.hourly_ops_report.get_settings", return_value=mock_settings),
            patch("src.tasks.hourly_ops_report.get_limits", return_value=mock_limits),
        ):
            ctx = {"bot": None, "sync_redis": None}
            await hourly_ops_report(ctx)

        assert "missing bot/redis" in caplog.text

    @pytest.mark.asyncio
    async def test_audit_query_failure_is_handled(
        self,
        mock_bot: AsyncMock,
        mock_redis: AsyncMock,
        mock_settings: Settings,
        mock_limits: Limits,
        mock_alerts: MagicMock,
    ) -> None:
        """Если audit_log ещё нет (до TASK-0057) — не падаем, errors только из system_events."""
        from src.tasks.hourly_ops_report import hourly_ops_report

        mock_redis.get.return_value = None

        with (
            patch("src.tasks.hourly_ops_report.AlertService", return_value=mock_alerts),
            patch("src.tasks.hourly_ops_report.get_settings", return_value=mock_settings),
            patch("src.tasks.hourly_ops_report.get_limits", return_value=mock_limits),
        ):
            mock_session = AsyncMock()
            calls = []

            async def fake_execute(sql):
                calls.append(str(sql))
                res = MagicMock()
                # Для audit simulate failure
                if "audit_log" in str(sql):
                    raise Exception("relation audit_log does not exist")
                res.scalar_one.return_value = 5 if "users" in str(sql) else 1
                return res

            mock_session.execute = fake_execute

            with patch("src.tasks.hourly_ops_report.get_session") as mock_get_session:
                mock_get_session.return_value.__aenter__.return_value = mock_session

                ctx = _ctx(bot=mock_bot, redis=mock_redis, settings=mock_settings)
                await hourly_ops_report(ctx)

        # errors должен быть из system (1), audit проигнорирован
        text = mock_alerts.send_ops.call_args[0][0]
        assert "ошибки 1" in text  # только sys
