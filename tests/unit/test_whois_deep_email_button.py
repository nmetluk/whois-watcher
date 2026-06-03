"""Тесты кнопки «✉️ Глубокий e-mail» на карточке /whois (TASK-0046).

Покрываем:
- Freshness gate по email_deep_cache.next_check_at
- Два пути: показ из кэша vs enqueue задачи
- Guard на размер callback_data
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import CallbackQuery, Message

from src.bot.handlers.whois import _show_deep_email_from_whois_card
from src.db.models import EmailDeepCache, User


def _make_deep_cache(*, next_check_at: datetime | None = None, **kwargs) -> EmailDeepCache:
    cache = MagicMock(spec=EmailDeepCache)
    cache.domain = kwargs.get("domain", "example.com")
    cache.next_check_at = next_check_at or (datetime.now(tz=UTC) + timedelta(hours=1))
    cache.spf = kwargs.get("spf")
    cache.mta_sts = kwargs.get("mta_sts")
    # ... остальные поля при необходимости
    return cache


class TestShowDeepEmailFromWhoisCard:
    def _make_query(self) -> CallbackQuery:
        query = MagicMock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.message = MagicMock(spec=Message)
        query.message.reply = AsyncMock()
        # for TASK-0075 deliver_chat_id
        query.message.chat = MagicMock()
        query.message.chat.id = 12345
        return query

    def _make_user(self) -> User:
        user = MagicMock(spec=User)
        user.id = 424242
        return user

    @pytest.mark.asyncio
    async def test_fresh_cache_renders_without_enqueue(self) -> None:
        """Свежий кэш → сразу показываем разбор, job не ставим."""
        query = self._make_query()
        user = self._make_user()
        arq_redis = AsyncMock()

        fresh_cache = _make_deep_cache(next_check_at=datetime.now(tz=UTC) + timedelta(hours=1))

        with (
            patch("src.bot.handlers.whois.get_session") as mock_session,
            patch("src.bot.handlers.whois.EmailDeepCacheRepository") as mock_repo_cls,
            patch("src.bot.handlers.whois.format_email_deep") as mock_formatter,
        ):
            mock_repo = MagicMock()
            mock_repo.get = AsyncMock(return_value=fresh_cache)
            mock_repo_cls.return_value = mock_repo
            mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_formatter.return_value = "✉️ Deep email report"

            await _show_deep_email_from_whois_card(
                query=query,
                user=user,
                lang="ru",
                domain="example.com",
                arq_redis=arq_redis,
            )

        arq_redis.enqueue_job.assert_not_called()
        query.message.reply.assert_called_once()
        assert "Deep email report" in str(query.message.reply.call_args)
        query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_stale_or_missing_cache_enqueues_job(self) -> None:
        """Пустой или протухший кэш → ставим задачу + сообщение «ищу…»."""
        query = self._make_query()
        user = self._make_user()
        arq_redis = AsyncMock()

        with (
            patch("src.bot.handlers.whois.get_session") as mock_session,
            patch("src.bot.handlers.whois.EmailDeepCacheRepository") as mock_repo_cls,
        ):
            mock_repo = MagicMock()
            mock_repo.get = AsyncMock(return_value=None)
            mock_repo_cls.return_value = mock_repo
            mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())

            await _show_deep_email_from_whois_card(
                query=query,
                user=user,
                lang="en",
                domain="example.com",
                arq_redis=arq_redis,
            )

        arq_redis.enqueue_job.assert_awaited_once_with(
            "check_email_deep", "example.com", deliver_chat_id=12345, deliver_lang="en"
        )
        query.message.reply.assert_called_once()
        query.answer.assert_called_once()

    def test_deep_email_callback_data_size_guard(self) -> None:
        """callback_data для deep_email кнопки ≤64 байт на длинном FQDN (TASK-0048: keyboards нормализует в registrable только для sub/deep)."""
        from src.bot.keyboards import WhoisAction
        from src.utils.domains import registrable_domain

        # Короткий
        data = WhoisAction(action="deep_email", domain="example.com").pack()
        assert len(data.encode("utf-8")) <= 64

        # Длинный FQDN (как пришло бы из whois-карточки поддомена)
        long_sub = "a" * 60 + ".example.com"
        # В keyboards для action=deep_email (и subdomains) мы теперь кладём registrable
        reg = registrable_domain(long_sub) or long_sub
        data_long = WhoisAction(action="deep_email", domain=reg).pack()
        assert len(data_long.encode("utf-8")) <= 64
        assert "example.com" in data_long
        assert len(long_sub.encode("utf-8")) > 64  # исходный не влез бы

        # Прямой конструктор с полным длинным FQDN для deep_email упадёт в aiogram (guard) — это ожидаемо;
        # именно поэтому мы нормализуем *внутри* whois_actions только для этих двух кнопок.
        # (Для follow/refresh/raw/wishlist переполнение — отдельный pre-existing долг, не в scope 0048.)
