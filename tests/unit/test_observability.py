"""Тесты ``src.observability.setup_sentry`` и фильтра ``before_send``.

Sentry SDK мы не дёргаем по-настоящему — только проверяем, что ``init``
зовётся с нужными аргументами и что ``_scrub_in_place`` чистит секреты.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from src.observability import _before_send, _scrub_in_place, setup_sentry


def _settings(*, env: str = "development", dsn: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(environment=env, log_level="INFO", sentry_dsn=dsn)


class TestSetupSentry:
    def test_no_dsn_is_noop(self) -> None:
        # Без DSN ``setup_sentry`` не должен импортировать sentry_sdk вообще —
        # вызов не падает, ничего не делается.
        with patch.dict("sys.modules"):
            setup_sentry(_settings(dsn=None))

    def test_with_dsn_inits_sentry(self) -> None:
        # Полная инициализация SDK имеет глобальные побочки — мокаем init.
        with patch("sentry_sdk.init") as init_mock:
            setup_sentry(_settings(dsn="https://example@sentry.test/1"))
        init_mock.assert_called_once()
        kwargs = init_mock.call_args.kwargs
        assert kwargs["dsn"] == "https://example@sentry.test/1"
        assert kwargs["environment"] == "development"
        assert kwargs["send_default_pii"] is False
        # ``before_send`` подключён
        assert callable(kwargs["before_send"])
        # Интеграции добавлены
        integration_names = {type(i).__name__ for i in kwargs["integrations"]}
        assert "AioHttpIntegration" in integration_names
        assert "SqlalchemyIntegration" in integration_names
        assert "RedisIntegration" in integration_names


class TestScrubInPlace:
    def test_filters_token_password_secret(self) -> None:
        event = {
            "extra": {
                "bot_token": "abc",
                "user_password": "x",
                "webhook_secret": "y",
                "user_id": 42,
            }
        }
        _scrub_in_place(event)
        extra = event["extra"]
        assert extra["bot_token"] == "[Filtered]"
        assert extra["user_password"] == "[Filtered]"
        assert extra["webhook_secret"] == "[Filtered]"
        assert extra["user_id"] == 42  # not filtered

    def test_filters_bulk_whois_data(self) -> None:
        event = {"contexts": {"raw_data": {"a": 1}, "raw_response": "..."}}
        _scrub_in_place(event)
        ctxs = event["contexts"]
        assert ctxs["raw_data"] == "[Filtered: bulk]"
        assert ctxs["raw_response"] == "[Filtered: bulk]"

    def test_handles_nested_lists(self) -> None:
        event = {"breadcrumbs": [{"data": {"api_key": "leak"}}, {"data": {"x": 1}}]}
        _scrub_in_place(event)
        assert event["breadcrumbs"][0]["data"]["api_key"] == "[Filtered]"
        assert event["breadcrumbs"][1]["data"]["x"] == 1

    def test_before_send_returns_event(self) -> None:
        event = {"extra": {"bot_token": "abc"}}
        out = _before_send(event, {})
        assert out is event
        assert event["extra"]["bot_token"] == "[Filtered]"
