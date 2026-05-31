"""Тесты кнопки «🛰 Поддомены» на карточке /whois (TASK-0042).

Проверяем:
- Freshness-гейт для subdomain_enum_cache
- Два пути: показ из свежего кэша vs enqueue задачи
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import CallbackQuery, Message

from src.bot.handlers.whois import _is_subdomain_cache_fresh, _show_subdomains_from_whois_card
from src.db.models import SubdomainEnumCache, User


def _make_cache(*, subdomains: list[str] | None = None, fetched_at: datetime | None = None):
    """Фабрика мок-объекта кэша поддоменов (с spec для anti-drift)."""
    cache = MagicMock(spec=SubdomainEnumCache)
    cache.subdomains = subdomains
    cache.fetched_at = fetched_at
    return cache


class TestIsSubdomainCacheFresh:
    """Тесты _is_subdomain_cache_fresh (7 дней).

    Важно: моками пользуемся через spec=SubdomainEnumCache (anti-drift, TASK-0045).
    getattr на ORM-моделях запрещён (см. CLAUDE.md).
    """

    def test_none_cache_is_not_fresh(self) -> None:
        assert _is_subdomain_cache_fresh(None) is False

    def test_missing_fetched_at_is_not_fresh(self) -> None:
        cache = _make_cache(subdomains=["www.example.com"], fetched_at=None)
        assert _is_subdomain_cache_fresh(cache) is False

    def test_fresh_cache_within_7_days(self) -> None:
        now = datetime.now(tz=UTC)
        cache = _make_cache(
            subdomains=["www.example.com"],
            fetched_at=now - timedelta(days=3),
        )
        assert _is_subdomain_cache_fresh(cache) is True

    def test_stale_cache_older_than_7_days(self) -> None:
        now = datetime.now(tz=UTC)
        cache = _make_cache(
            subdomains=["www.example.com"],
            fetched_at=now - timedelta(days=8),
        )
        assert _is_subdomain_cache_fresh(cache) is False


class TestShowSubdomainsFromWhoisCard:
    """Интеграционные юнит-тесты хэндлера кнопки (моки)."""

    def _make_query(self) -> CallbackQuery:
        query = MagicMock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.message = MagicMock(spec=Message)
        query.message.reply = AsyncMock()
        return query

    def _make_user(self) -> User:
        user = MagicMock(spec=User)
        user.id = 424242
        return user

    @pytest.mark.asyncio
    async def test_fresh_cache_shows_result_without_enqueue(self) -> None:
        """Свежий кэш → сразу показываем список, job не ставим."""
        query = self._make_query()
        user = self._make_user()
        arq_redis = AsyncMock()

        fresh_cache = _make_cache(
            subdomains=["www1.example.com", "www2.example.com"],
            fetched_at=datetime.now(tz=UTC) - timedelta(hours=10),
        )

        with (
            patch("src.bot.handlers.whois.get_session") as mock_session,
            patch("src.bot.handlers.whois.SubdomainEnumCacheRepository") as mock_repo_cls,
        ):
            mock_repo = MagicMock()
            mock_repo.get = AsyncMock(return_value=fresh_cache)
            mock_repo_cls.return_value = mock_repo

            # Мокаем get_session как async context manager
            mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())

            await _show_subdomains_from_whois_card(
                query=query,
                user=user,
                lang="ru",
                domain="example.com",
                arq_redis=arq_redis,
            )

        # Не должно быть enqueue
        arq_redis.enqueue_job.assert_not_called()
        # Должно ответить пользователю списком
        query.message.reply.assert_called_once()
        # Должен ответить на callback
        query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_or_stale_cache_enqueues_job(self) -> None:
        """Нет кэша или протух → ставим задачу check_subdomains."""
        query = self._make_query()
        user = self._make_user()
        arq_redis = AsyncMock()

        with (
            patch("src.bot.handlers.whois.get_session") as mock_session,
            patch("src.bot.handlers.whois.SubdomainEnumCacheRepository") as mock_repo_cls,
        ):
            mock_repo = MagicMock()
            mock_repo.get = AsyncMock(return_value=None)  # нет кэша
            mock_repo_cls.return_value = mock_repo
            mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())

            await _show_subdomains_from_whois_card(
                query=query,
                user=user,
                lang="en",
                domain="example.com",
                arq_redis=arq_redis,
            )

        arq_redis.enqueue_job.assert_awaited_once_with("check_subdomains", "example.com")
        query.message.reply.assert_called_once()  # сообщение «ищу…»
        query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_very_long_domain_is_handled_safely(self) -> None:
        """Очень длинный домен не должен падать с исключением (защита callback_data)."""
        query = self._make_query()
        user = self._make_user()
        arq_redis = AsyncMock()

        # Этот домен слишком длинный для некоторых путей, но главное — не упасть
        long_domain = "a" * 200 + ".com"

        with (
            patch("src.bot.handlers.whois.get_session") as mock_session,
            patch("src.bot.handlers.whois.SubdomainEnumCacheRepository") as mock_repo_cls,
        ):
            mock_repo = MagicMock()
            mock_repo.get = AsyncMock(return_value=None)
            mock_repo_cls.return_value = mock_repo
            mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())

            # Не должен поднять исключение
            await _show_subdomains_from_whois_card(
                query=query,
                user=user,
                lang="ru",
                domain=long_domain,
                arq_redis=arq_redis,
            )

        # В любом случае должен ответить на коллбэк
        query.answer.assert_awaited()
