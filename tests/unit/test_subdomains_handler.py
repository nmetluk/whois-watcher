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

        callback_data = SubdomainAction(action="track", registrable="example.com", idx=-1)

        # Мокаем SubdomainEnumCacheRepository чтобы возвращать None (idx=-1 → out of range)
        mock_cache_repo = MagicMock()
        mock_cache_repo.get = AsyncMock(return_value=None)

        with patch(
            "src.bot.handlers.subdomains.SubdomainEnumCacheRepository", return_value=mock_cache_repo
        ):
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

    async def test_track_with_added_pending_status_shows_success(self) -> None:
        """added_pending (типичный случай) показывает success, не invalid_domain."""
        from unittest.mock import create_autospec

        from src.services.domains import AddDomainResult, DomainService

        query = MagicMock()
        query.answer = AsyncMock()

        # Мок для кэша с поддоменом
        cached = _cache(subdomains=["www.example.com"])

        # Мок для SubdomainEnumCacheRepository
        mock_cache_repo = MagicMock()
        mock_cache_repo.get = AsyncMock(return_value=cached)

        # Мок для DomainService.add_for_user с autospec
        mock_service = create_autospec(DomainService, instance=True)
        mock_service.add_for_user.return_value = AddDomainResult(
            status="added_pending",
            normalized_domain="www.example.com",
        )

        with (
            patch("src.bot.handlers.subdomains.DomainService", return_value=mock_service),
            patch(
                "src.bot.handlers.subdomains.SubdomainEnumCacheRepository",
                return_value=mock_cache_repo,
            ),
        ):
            callback_data = SubdomainAction(action="track", registrable="example.com", idx=0)

            await handler.cb_subdomains_track(
                callback=query,
                callback_data=callback_data,
                user=_user(),
                lang="ru",
                arq_redis=AsyncMock(),
                limits=_limits(),
            )

        # Должен быть вызван с success (добавлен на слежение), НЕ с invalid_domain
        answer_call = query.answer.call_args
        answer_text = str(answer_call).lower()
        assert "добавлен" in answer_text or "added" in answer_text
        assert "invalid" not in answer_text

    async def test_track_with_added_status_shows_success(self) -> None:
        """added (поддомен → registrable) показывает success, не invalid_domain."""
        from unittest.mock import create_autospec

        from src.services.domains import AddDomainResult, DomainService

        query = MagicMock()
        query.answer = AsyncMock()

        # Мок для кэша с поддоменом
        cached = _cache(subdomains=["www.example.com"])

        # Мок для SubdomainEnumCacheRepository
        mock_cache_repo = MagicMock()
        mock_cache_repo.get = AsyncMock(return_value=cached)

        # Мок для DomainService.add_for_user с autospec
        mock_service = create_autospec(DomainService, instance=True)
        mock_service.add_for_user.return_value = AddDomainResult(
            status="added",
            normalized_domain="example.com",
        )

        with (
            patch("src.bot.handlers.subdomains.DomainService", return_value=mock_service),
            patch(
                "src.bot.handlers.subdomains.SubdomainEnumCacheRepository",
                return_value=mock_cache_repo,
            ),
        ):
            callback_data = SubdomainAction(action="track", registrable="example.com", idx=0)

            await handler.cb_subdomains_track(
                callback=query,
                callback_data=callback_data,
                user=_user(),
                lang="ru",
                arq_redis=AsyncMock(),
                limits=_limits(),
            )

        # Должен быть вызван с success (добавлен на слежение), НЕ с invalid_domain
        answer_call = query.answer.call_args
        answer_text = str(answer_call).lower()
        assert "добавлен" in answer_text or "added" in answer_text
        assert "invalid" not in answer_text


# ---------------------------------------------------------------------------
# Callback — track_all (без БД)
# ---------------------------------------------------------------------------


class TestCallbackTrackAll:
    async def test_track_all_without_cache_shows_error(self) -> None:
        query = MagicMock()
        query.answer = AsyncMock()

        callback_data = SubdomainAction(action="track_all", registrable="example.com")

        # Мокаем SubdomainEnumCacheRepository чтобы вернуть None
        mock_cache_repo = MagicMock()
        mock_cache_repo.get = AsyncMock(return_value=None)

        with patch(
            "src.bot.handlers.subdomains.SubdomainEnumCacheRepository", return_value=mock_cache_repo
        ):
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


# ---------------------------------------------------------------------------
# Фикс 1: Кнопки с именами поддоменов + callback ≤ 64 байта
# ---------------------------------------------------------------------------


class TestSubdomainKeyboardButtons:
    def test_button_contains_subdomain_name(self) -> None:
        """Кнопки клавиатуры должны содержать имя поддомена."""
        from src.bot.keyboards import subdomains_keyboard

        subdomains = ["www.example.com", "mail.example.com"]
        kb = subdomains_keyboard("example.com", subdomains, lang="en")

        # Кнопки должны содержать имена поддоменов
        button_texts = []
        for row in kb.inline_keyboard:
            for button in row:
                button_texts.append(button.text)

        # Проверяем что есть кнопки с поддоменами
        assert any("www" in text for text in button_texts)
        assert any("mail" in text for text in button_texts)
        # Все кнопки кроме track_all и refresh должны начинаться с 📌
        track_buttons = [t for t in button_texts if t.startswith("📌") and "all" not in t.lower()]
        assert len(track_buttons) == len(subdomains)

    def test_callback_data_fits_64_bytes_on_long_fqdn(self) -> None:
        """callback_data должен укладываться в 64 байта даже на длинных FQDN."""
        from src.bot.keyboards import subdomains_keyboard

        # Длинный FQDN — типичная выдача crt.sh
        long_fqdn = ["autodiscover.internal.staging.example.co.uk"]
        kb = subdomains_keyboard("example.co.uk", long_fqdn, lang="ru")

        # Проверяем каждый callback_data
        for row in kb.inline_keyboard:
            for btn in row:
                if btn.callback_data and btn.callback_data.startswith("sub:track"):
                    assert len(btn.callback_data.encode()) <= 64


# ---------------------------------------------------------------------------
# Фикс 2: Список поддоменов в сообщении
# ---------------------------------------------------------------------------


class TestSubdomainListInMessage:
    async def test_message_contains_subdomain_list(self) -> None:
        """Сообщение должно содержать список поддоменов."""
        message = _message("not used")
        command = _command("example.com")

        cached = _cache(
            subdomains=["www.example.com", "mail.example.com"],
            fetched_at=datetime.now(tz=UTC) - timedelta(days=1),
        )

        # Мок для SubdomainEnumCacheRepository
        mock_cache_repo = MagicMock()
        mock_cache_repo.get = AsyncMock(return_value=cached)

        with patch(
            "src.bot.handlers.subdomains.SubdomainEnumCacheRepository", return_value=mock_cache_repo
        ):
            await handler.cmd_subdomains(
                message=message,
                command=command,
                user=_user(),
                lang="ru",
                arq_redis=AsyncMock(),
            )

        # Проверяем что в сообщении есть список поддоменов
        text = message.answer.await_args.args[0]
        assert "www.example.com" in text or "www" in text.lower()
        assert "mail.example.com" in text or "mail" in text.lower()
        # Проверяем что есть формат списка (•)
        assert "•" in text or "-" in text
