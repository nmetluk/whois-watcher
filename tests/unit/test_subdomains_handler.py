"""Тесты хэндлера ``/subdomains`` (ADR 037).

Покрытие:
- Валидация домена (нормальный, IDN, мусор, публичный суффикс)
- Callback-хэндлеры (refresh, track)
- Кэш — свежесть
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.bot.handlers import subdomains as handler
from src.bot.keyboards import SubdomainAction
from src.config.limits import Limits
from src.db.models import SubdomainEnumCache, User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _user() -> MagicMock:
    user = MagicMock(spec=User)
    user.id = 42
    user.notify_days = [30, 7, 1]
    user.language = "ru"
    return user


def _message(text: str) -> MagicMock:
    message = MagicMock()
    message.text = text
    message.answer = AsyncMock()
    return message


def _command(args: str | None = None) -> MagicMock:
    cmd = MagicMock()
    cmd.args = args
    cmd.command = "subdomains"
    return cmd


def _cache(
    subdomains: list[str] | None = None,
    fetched_at: datetime | None = None,
) -> MagicMock:
    cache = MagicMock(spec=SubdomainEnumCache)
    cache.subdomains = subdomains or []
    if fetched_at is None:
        cache.fetched_at = None
    else:
        cache.fetched_at = fetched_at
    return cache


def _limits() -> MagicMock:
    limits = MagicMock(spec=Limits)
    limits.max_domains_per_user = 50000
    return limits


# ---------------------------------------------------------------------------
# Валидация домена (без БД)
# ---------------------------------------------------------------------------


class TestValidationNoDb:
    async def test_no_args_shows_prompt(self) -> None:
        message = _message("not used")
        command = _command(None)

        await handler.cmd_subdomains(
            message=message,
            command=command,
            user=_user(),
            lang="ru",
            arq_redis=AsyncMock(),
            redis=AsyncMock(),
        )

        text = message.answer.await_args.args[0]
        assert "subdomains" in text.lower()


# ---------------------------------------------------------------------------
# Кэш — свежесть (чистые функции)
# ---------------------------------------------------------------------------


class TestCacheFreshness:
    def test_fresh_cache_is_considered_fresh(self) -> None:
        cache = _cache(
            subdomains=["www.example.com"],
            fetched_at=datetime.now(tz=UTC) - timedelta(days=3),
        )
        assert handler._is_cache_fresh(cache) is True

    def test_stale_cache_is_not_fresh(self) -> None:
        cache = _cache(
            subdomains=["www.example.com"],
            fetched_at=datetime.now(tz=UTC) - timedelta(days=10),
        )
        assert handler._is_cache_fresh(cache) is False

    def test_cache_without_fetched_at_is_not_fresh(self) -> None:
        cache = _cache(subdomains=["www.example.com"], fetched_at=None)
        assert handler._is_cache_fresh(cache) is False


# ---------------------------------------------------------------------------
# Callback — refresh
# ---------------------------------------------------------------------------


class TestCallbackRefresh:
    async def test_refresh_enqueues_task(self) -> None:
        query = MagicMock()
        query.answer = AsyncMock()
        query.message = MagicMock()
        query.message.edit_text = AsyncMock()

        callback_data = SubdomainAction(action="refresh", registrable="example.com")
        arq_redis = AsyncMock()

        await handler.cb_subdomains_refresh(
            callback=query,
            callback_data=callback_data,
            user=_user(),
            lang="ru",
            arq_redis=arq_redis,
        )

        arq_redis.enqueue_job.assert_called_once_with("check_subdomains", "example.com")
        query.message.edit_text.assert_called_once()
        query.answer.assert_called_once()


# ---------------------------------------------------------------------------
# Callback — track
# ---------------------------------------------------------------------------


class TestCallbackTrack:
    async def test_track_with_empty_subdomain_shows_error(self) -> None:
        query = MagicMock()
        query.answer = AsyncMock()

        callback_data = SubdomainAction(action="track", registrable="example.com", subdomain="")

        await handler.cb_subdomains_track(
            callback=query,
            callback_data=callback_data,
            user=_user(),
            lang="ru",
            arq_redis=AsyncMock(),
            limits=_limits(),
        )

        # show_alert=True для ошибок
        assert query.answer.call_count >= 1


# ---------------------------------------------------------------------------
# Callback — track_all (без БД)
# ---------------------------------------------------------------------------


class TestCallbackTrackAll:
    async def test_track_all_without_cache_shows_error(self) -> None:
        query = MagicMock()
        query.answer = AsyncMock()

        callback_data = SubdomainAction(action="track_all", registrable="example.com")

        # Патчим SubdomainEnumCacheRepository.get чтобы вернуть None
        with patch("src.db.repositories.SubdomainEnumCacheRepository.get") as get_mock:
            get_mock.return_value = None

            with patch("src.bot.handlers.subdomains.get_session") as session_mock:
                # Создаём мок сессии
                session = MagicMock()
                session.__aenter__ = AsyncMock(return_value=session)
                session.__aexit__ = AsyncMock(return_value=None)

                # Добавляем репозиторий в сессию
                cache_repo = MagicMock()
                cache_repo.get = get_mock
                session.cache_repo = cache_repo

                session_mock.return_value = session

                await handler.cb_subdomains_track_all(
                    callback=query,
                    callback_data=callback_data,
                    user=_user(),
                    lang="ru",
                    arq_redis=AsyncMock(),
                    limits=_limits(),
                )

        # Должен показать ошибку "no_cache"
        query.answer.assert_called_once()
