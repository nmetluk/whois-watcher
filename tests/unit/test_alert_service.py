"""Тесты ``src.services.alerts.AlertService``.

Bot и Redis замоксены. Проверяем:

- дедупликация: повторный вызов с тем же ``severity+title+details[:200]``
  не приводит к второму ``send_message``
- ``admin_channel_id=None`` → no-op
- ошибка отправки Telegram не валит вызывающий код
- формат сообщения: тэг ``#severity``, заголовок, тело
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from src.config.limits import Limits
from src.config.settings import Settings
from src.services.alerts import (
    AlertService,
    _dedup_key,
    _format_alert,
    _format_daily_summary,
    instance_tag,
)


def _make_settings(
    *,
    channel_id: int | None = -1001234567890,
    instance_name: str = "",
    instance_domain: str = "",
    server_ip: str = "",
) -> MagicMock:
    s = MagicMock(spec=Settings)
    s.admin_channel_id = channel_id
    s.environment = "development"
    s.instance_name = instance_name
    s.instance_domain = instance_domain
    s.server_ip = server_ip
    return s


def _make_limits() -> Limits:
    return Limits(alert_dedup_ttl_minutes=10)


def _make_redis(*, reserved: bool = True) -> AsyncMock:
    redis = AsyncMock()
    # set(... nx=True) → True если ключ был свободен.
    redis.set.return_value = True if reserved else None
    return redis


class TestAlertService:
    async def test_send_critical_calls_bot(self) -> None:
        bot = AsyncMock()
        redis = _make_redis()
        alerts = AlertService(
            bot=bot, redis=redis, settings=_make_settings(), limits=_make_limits()
        )
        await alerts.send_critical("title", "details")
        bot.send_message.assert_called_once()
        kwargs = bot.send_message.call_args.kwargs
        assert kwargs["chat_id"] == -1001234567890
        assert "#critical" in kwargs["text"]
        assert "title" in kwargs["text"]
        assert "details" in kwargs["text"]

    async def test_send_info_calls_bot(self) -> None:
        bot = AsyncMock()
        alerts = AlertService(
            bot=bot, redis=_make_redis(), settings=_make_settings(), limits=_make_limits()
        )
        await alerts.send_info("started", "env=dev")
        bot.send_message.assert_called_once()
        assert "#info" in bot.send_message.call_args.kwargs["text"]

    async def test_send_anomaly_uses_anomaly_tag(self) -> None:
        bot = AsyncMock()
        alerts = AlertService(
            bot=bot, redis=_make_redis(), settings=_make_settings(), limits=_make_limits()
        )
        await alerts.send_anomaly("whois 50% fail", "rdap timeouts")
        assert "#anomaly" in bot.send_message.call_args.kwargs["text"]

    async def test_admin_channel_none_is_noop(self) -> None:
        bot = AsyncMock()
        redis = _make_redis()
        alerts = AlertService(
            bot=bot,
            redis=redis,
            settings=_make_settings(channel_id=None),
            limits=_make_limits(),
        )
        await alerts.send_critical("title", "details")
        bot.send_message.assert_not_called()
        # До Redis тоже не дошли — рано вышли.
        redis.set.assert_not_called()

    async def test_dedup_suppresses_second_call(self) -> None:
        bot = AsyncMock()
        redis = AsyncMock()
        # Первый раз — свободно (True), второй раз — занято (None).
        redis.set.side_effect = [True, None]
        alerts = AlertService(
            bot=bot, redis=redis, settings=_make_settings(), limits=_make_limits()
        )
        await alerts.send_critical("same", "details")
        await alerts.send_critical("same", "details")
        assert bot.send_message.call_count == 1

    async def test_telegram_failure_swallowed(self) -> None:
        """Алерт не должен валить вызывающий код, даже если Telegram упал."""
        bot = AsyncMock()
        bot.send_message.side_effect = RuntimeError("telegram is down")
        alerts = AlertService(
            bot=bot, redis=_make_redis(), settings=_make_settings(), limits=_make_limits()
        )
        # Не должно бросить
        await alerts.send_critical("title", "details")
        bot.send_message.assert_called_once()

    async def test_send_daily_summary_formats_dict(self) -> None:
        bot = AsyncMock()
        redis = _make_redis()
        alerts = AlertService(
            bot=bot, redis=redis, settings=_make_settings(), limits=_make_limits()
        )
        await alerts.send_daily_summary(
            {"new_users": 3, "domains_added": 12, "notifications": {"expiry": 5}}
        )
        text = bot.send_message.call_args.kwargs["text"]
        assert "#daily" in text
        assert "new_users: 3" in text
        assert "expiry: 5" in text

    async def test_send_with_instance_tag(self) -> None:
        bot = AsyncMock()
        redis = _make_redis()
        alerts = AlertService(
            bot=bot,
            redis=redis,
            settings=_make_settings(
                instance_name="prod-admin",
                instance_domain="whois.example.com",
                server_ip="5.188.88.78",
            ),
            limits=_make_limits(),
        )
        await alerts.send_critical("title", "details")
        text = bot.send_message.call_args.kwargs["text"]
        assert "[prod-admin · whois.example.com · 5.188.88.78]" in text
        assert "#critical" in text


class TestFormatters:
    def test_format_alert_has_icon_and_severity(self) -> None:
        out = _format_alert(severity="critical", icon="🚨", title="t", details="d")
        assert out.startswith("🚨 #critical")
        assert "t" in out
        assert "d" in out

    def test_format_alert_no_body_when_details_empty(self) -> None:
        out = _format_alert(severity="info", icon="ℹ️", title="t", details="")
        assert out == "ℹ️ #info\nt"

    def test_dedup_key_stable_for_same_inputs(self) -> None:
        a = _dedup_key(severity="info", title="x", details="y")
        b = _dedup_key(severity="info", title="x", details="y")
        assert a == b

    def test_dedup_key_changes_with_severity(self) -> None:
        a = _dedup_key(severity="info", title="x", details="y")
        b = _dedup_key(severity="critical", title="x", details="y")
        assert a != b

    def test_format_daily_summary_handles_lists_and_dicts(self) -> None:
        text = _format_daily_summary(
            {
                "users": 10,
                "notifications": {"expiry": 3, "ns_change": 1},
                "top_errors": ["whois_failed: 5", "rate_limit_hit: 2"],
            }
        )
        assert "users: 10" in text
        assert "notifications:" in text
        assert "expiry: 3" in text
        assert "top_errors:" in text
        assert "whois_failed: 5" in text

    def test_format_daily_summary_empty_dict(self) -> None:
        assert _format_daily_summary({}) == "(no data)"


class TestInstanceTag:
    def test_instance_tag_collects_all_parts(self) -> None:
        s = MagicMock(spec=Settings)
        s.instance_name = "prod-admin"
        s.instance_domain = "whois.example.com"
        s.server_ip = "5.188.88.78"
        assert instance_tag(s) == "prod-admin · whois.example.com · 5.188.88.78"

    def test_instance_tag_skips_empty_parts(self) -> None:
        s = MagicMock(spec=Settings)
        s.instance_name = ""
        s.instance_domain = "whois.example.com"
        s.server_ip = ""
        assert instance_tag(s) == "whois.example.com"

    def test_instance_tag_empty_when_all_empty(self) -> None:
        s = MagicMock(spec=Settings)
        s.instance_name = ""
        s.instance_domain = ""
        s.server_ip = ""
        assert instance_tag(s) == ""

    def test_instance_tag_name_only(self) -> None:
        s = MagicMock(spec=Settings)
        s.instance_name = "worker-1"
        s.instance_domain = ""
        s.server_ip = ""
        assert instance_tag(s) == "worker-1"

    def test_format_alert_includes_tag_when_provided(self) -> None:
        out = _format_alert(
            severity="critical", icon="🚨", title="t", details="d", tag="prod · bot.example.com"
        )
        assert out.startswith("[prod · bot.example.com]")
        assert "#critical" in out

    def test_format_alert_no_tag_when_empty(self) -> None:
        out = _format_alert(severity="info", icon="ℹ️", title="t", details="d", tag="")
        assert out.startswith("ℹ️ #info")
        assert "[" not in out
