"""Тесты ARQ-задачи ``send_expiry_reminder``.

Всё, что касается БД и aiogram, замоксено. Проверяем:

- skip при ``notify_expiry=false``
- skip при ``is_blocked``
- happy path: send_message с правильным chat_id + record_sent
- дедупликация: при ``was_sent=True`` — выходим без send_message
- ``TelegramForbiddenError`` → ``is_blocked=True`` + record_sent (чтобы
  не пытаться повторно на следующих тиках)
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.exceptions import TelegramForbiddenError

from src.tasks import send_reminders


def _async_cm(value: object) -> MagicMock:
    """Build a MagicMock acting as ``async with`` that yields ``value``."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=value)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.fixture
def patches() -> Iterator[dict[str, MagicMock]]:
    """Patch get_session + all four repository classes inside send_reminders."""
    with (
        patch.object(send_reminders, "get_session") as gs,
        patch.object(send_reminders, "DomainRepository") as dr_cls,
        patch.object(send_reminders, "NotificationRepository") as nr_cls,
        patch.object(send_reminders, "UserRepository") as ur_cls,
        patch.object(send_reminders, "WhoisCacheRepository") as wr_cls,
    ):
        session = MagicMock(name="session")
        gs.return_value = _async_cm(session)
        yield {
            "session": session,
            "domain_repo": dr_cls.return_value,
            "notif_repo": nr_cls.return_value,
            "user_repo": ur_cls.return_value,
            "cache_repo": wr_cls.return_value,
        }


def _ud(notify_expiry: bool = True) -> MagicMock:
    ud = MagicMock(name="user_domain")
    ud.notify_expiry = notify_expiry
    return ud


def _user(*, blocked: bool = False, lang: str = "ru", tg_id: int = 9999) -> MagicMock:
    u = MagicMock(name="user")
    u.is_blocked = blocked
    u.language = lang
    u.telegram_id = tg_id
    return u


def _cache(expires: datetime | None) -> MagicMock:
    c = MagicMock(name="cache")
    c.expires_at = expires
    c.registrar = "RU-CENTER"
    return c


class TestSendExpiryReminder:
    async def test_skip_when_notify_expiry_false(self, patches: dict[str, MagicMock]) -> None:
        patches["domain_repo"].get_for_user = AsyncMock(return_value=_ud(notify_expiry=False))
        bot = AsyncMock()

        await send_reminders.send_expiry_reminder(
            {"bot": bot}, user_id=1, domain="example.ru", days_before=7
        )

        bot.send_message.assert_not_called()

    async def test_skip_when_user_blocked(self, patches: dict[str, MagicMock]) -> None:
        patches["domain_repo"].get_for_user = AsyncMock(return_value=_ud())
        patches["user_repo"].get_by_ids = AsyncMock(return_value=[_user(blocked=True)])
        bot = AsyncMock()

        await send_reminders.send_expiry_reminder(
            {"bot": bot}, user_id=1, domain="example.ru", days_before=7
        )

        bot.send_message.assert_not_called()

    async def test_skip_when_already_sent(self, patches: dict[str, MagicMock]) -> None:
        patches["domain_repo"].get_for_user = AsyncMock(return_value=_ud())
        patches["user_repo"].get_by_ids = AsyncMock(return_value=[_user()])
        patches["cache_repo"].get = AsyncMock(
            return_value=_cache(datetime(2027, 3, 15, tzinfo=UTC))
        )
        patches["notif_repo"].was_sent = AsyncMock(return_value=True)
        bot = AsyncMock()

        await send_reminders.send_expiry_reminder(
            {"bot": bot}, user_id=1, domain="example.ru", days_before=7
        )

        bot.send_message.assert_not_called()
        patches["notif_repo"].record_sent.assert_not_called()

    async def test_happy_path_sends_and_records(self, patches: dict[str, MagicMock]) -> None:
        expires = datetime(2027, 3, 15, tzinfo=UTC)
        patches["domain_repo"].get_for_user = AsyncMock(return_value=_ud())
        patches["user_repo"].get_by_ids = AsyncMock(return_value=[_user(tg_id=42)])
        patches["cache_repo"].get = AsyncMock(return_value=_cache(expires))
        patches["notif_repo"].was_sent = AsyncMock(return_value=False)
        patches["notif_repo"].record_sent = AsyncMock(return_value=True)
        bot = AsyncMock()

        await send_reminders.send_expiry_reminder(
            {"bot": bot}, user_id=1, domain="example.ru", days_before=7
        )

        bot.send_message.assert_awaited_once()
        kwargs = bot.send_message.await_args.kwargs
        assert kwargs["chat_id"] == 42
        assert "example.ru" in kwargs["text"]
        patches["notif_repo"].record_sent.assert_awaited_once()

    async def test_forbidden_marks_blocked_and_records(self, patches: dict[str, MagicMock]) -> None:
        expires = datetime(2027, 3, 15, tzinfo=UTC)
        patches["domain_repo"].get_for_user = AsyncMock(return_value=_ud())
        patches["user_repo"].get_by_ids = AsyncMock(return_value=[_user(tg_id=42)])
        patches["cache_repo"].get = AsyncMock(return_value=_cache(expires))
        patches["notif_repo"].was_sent = AsyncMock(return_value=False)
        patches["notif_repo"].record_sent = AsyncMock(return_value=True)
        patches["user_repo"].update_settings = AsyncMock()
        bot = AsyncMock()
        bot.send_message = AsyncMock(
            side_effect=TelegramForbiddenError(method=MagicMock(), message="blocked")
        )

        await send_reminders.send_expiry_reminder(
            {"bot": bot}, user_id=1, domain="example.ru", days_before=7
        )

        # user marked blocked + record_sent чтобы не дёргать снова
        patches["user_repo"].update_settings.assert_awaited_with(1, is_blocked=True)
        patches["notif_repo"].record_sent.assert_awaited_once()
