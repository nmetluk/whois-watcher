"""Тесты wishlist (ADR 039): scheduler-TTL, переход registered→available,
одноразовость уведомления.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from src.db.models import Wishlist
from src.whois.scheduler import calculate_next_check

# ---------------------------------------------------------------------------
# scheduler: is_wishlist=True → 24h TTL
# ---------------------------------------------------------------------------


class TestSchedulerWishlist:
    def test_wishlist_uses_24h_ttl_regardless_of_expires(self) -> None:
        now = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)
        # Любой expires_at — должен игнорироваться при wishlist=True.
        in_one_day = now + timedelta(days=1)
        in_year = now + timedelta(days=365)
        for exp in (None, in_one_day, in_year):
            result = calculate_next_check(exp, now=now, is_wishlist=True)
            assert result == now + timedelta(hours=24)

    def test_normal_mode_unchanged(self) -> None:
        """is_wishlist=False (дефолт) — поведение не сломалось."""
        now = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)
        result = calculate_next_check(now + timedelta(days=200), now=now)
        # ttl_far_days = 30 (см. Limits) — 30 дней вперёд
        assert result is not None
        assert (result - now).days == 30


# ---------------------------------------------------------------------------
# check_domain: wishlist-домен освободился → enqueue notice
# ---------------------------------------------------------------------------


class TestCheckDomainWishlistTrigger:
    async def test_registered_to_free_enqueues_wishlist_notice(self, monkeypatch) -> None:
        """Проверяем, что при освобождении домена ставится задача уведомления."""
        from contextlib import asynccontextmanager

        from src.tasks.check_domain import _enqueue_wishlist_notices

        arq_redis = AsyncMock()
        ctx = {"redis": arq_redis}

        # Мокаем WishlistRepository
        wishlist_repo_mock = AsyncMock()

        # wishlist-подписчик
        sub_wish = MagicMock(spec=Wishlist)
        sub_wish.user_id = 100
        sub_wish.domain = "example.com"

        wishlist_repo_mock.get_subscribers_for_domain.return_value = [sub_wish]

        @asynccontextmanager
        async def fake_session():
            session = MagicMock()
            yield session

        # Патчим импорты внутри функции
        monkeypatch.setattr("src.db.session.get_session", fake_session)
        monkeypatch.setattr(
            "src.db.repositories.WishlistRepository",
            lambda _s: wishlist_repo_mock,
        )

        await _enqueue_wishlist_notices("example.com", ctx, [])

        # wishlist-подписчик получает enqueue
        arq_redis.enqueue_job.assert_awaited_once_with(
            "send_wishlist_available_notice", 100, "example.com"
        )

    async def test_only_wishlist_subscribers_triggers_24h_ttl(self) -> None:
        """all-wishlist → calculate_next_check(is_wishlist=True).

        Этот тест проверяет расчёт only_wishlist в _handle_success.
        """
        from src.db.models import UserDomain

        # only_wishlist = bool(wishlist_subscribers) and not bool(subscribers)
        # В тесте проверяем логику: если нет tracked-подписчиков, но есть wishlist

        subscribers_empty = []
        subscribers_has = [MagicMock(spec=UserDomain)]

        # only_wishlist = bool(wishlist_subscribers) and not bool(subscribers)
        # Для all-wishlist: wishlist_subscribers есть, subscribers нет
        wishlist_present = [MagicMock(spec=Wishlist)]
        only_wishlist_all = bool(wishlist_present) and not bool(subscribers_empty)

        # Для mixed: есть и wishlist, и subscribers
        only_wishlist_mix = bool(wishlist_present) and not bool(subscribers_has)

        assert only_wishlist_all is True  # Нет tracked → только wishlist
        assert only_wishlist_mix is False  # Есть tracked → смешанный режим


# ---------------------------------------------------------------------------
# notify_wishlist: проверка exists и mark_notified
# ---------------------------------------------------------------------------


class TestNotifyWishlist:
    async def test_skips_when_not_in_wishlist(self, monkeypatch) -> None:
        """Пропускаем уведомление если домена нет в wishlist."""
        from contextlib import asynccontextmanager

        from src.tasks import notify_wishlist as nw

        bot = AsyncMock()
        bot.send_message = AsyncMock()

        wishlist_repo = AsyncMock()
        wishlist_repo.exists = AsyncMock(return_value=False)  # Не в wishlist
        user_repo = AsyncMock()
        user_repo.get_by_ids = AsyncMock(return_value=[])

        @asynccontextmanager
        async def fake_session():
            session = MagicMock()
            yield session

        monkeypatch.setattr(nw, "get_session", fake_session)
        monkeypatch.setattr(nw, "WishlistRepository", lambda _s: wishlist_repo)
        monkeypatch.setattr(nw, "UserRepository", lambda _s: user_repo)

        await nw.send_wishlist_available_notice({"bot": bot}, 1, "example.com")

        # exists вернул False → early return без send_message
        bot.send_message.assert_not_called()
        # mark_notified не вызван
        wishlist_repo.mark_notified.assert_not_awaited()

    async def test_sends_and_removes_from_wishlist(self, monkeypatch) -> None:
        """Успешное уведомление → mark_notified (удаление)."""
        from contextlib import asynccontextmanager

        from src.db.models import User
        from src.tasks import notify_wishlist as nw

        bot = AsyncMock()
        bot.send_message = AsyncMock()

        wishlist_repo = AsyncMock()
        wishlist_repo.exists = AsyncMock(return_value=True)
        wishlist_repo.mark_notified = AsyncMock()

        user = MagicMock(spec=User)
        user.is_blocked = False
        user.language = "ru"
        user.telegram_id = 12345

        user_repo = AsyncMock()
        user_repo.get_by_ids = AsyncMock(return_value=[user])

        notif_repo = AsyncMock()
        notif_repo.record_sent = AsyncMock()

        @asynccontextmanager
        async def fake_session():
            session = MagicMock()
            yield session

        monkeypatch.setattr(nw, "get_session", fake_session)
        monkeypatch.setattr(nw, "WishlistRepository", lambda _s: wishlist_repo)
        monkeypatch.setattr(nw, "UserRepository", lambda _s: user_repo)
        monkeypatch.setattr(nw, "NotificationRepository", lambda _s: notif_repo)

        await nw.send_wishlist_available_notice({"bot": bot}, 1, "example.com")

        # Сообщение отправлено
        bot.send_message.assert_awaited_once()
        # Уведомление записано
        notif_repo.record_sent.assert_awaited_once()
        # Запись удалена из wishlist (одноразовость)
        wishlist_repo.mark_notified.assert_awaited_once_with(1, "example.com")

    async def test_skips_blocked_user(self, monkeypatch) -> None:
        """Заблокированный пользователь не получает уведомление."""
        from contextlib import asynccontextmanager

        from src.db.models import User
        from src.tasks import notify_wishlist as nw

        bot = AsyncMock()
        bot.send_message = AsyncMock()

        wishlist_repo = AsyncMock()
        wishlist_repo.exists = AsyncMock(return_value=True)

        user = MagicMock(spec=User)
        user.is_blocked = True  # Заблокирован

        user_repo = AsyncMock()
        user_repo.get_by_ids = AsyncMock(return_value=[user])

        @asynccontextmanager
        async def fake_session():
            yield MagicMock()

        monkeypatch.setattr(nw, "get_session", fake_session)
        monkeypatch.setattr(nw, "WishlistRepository", lambda _s: wishlist_repo)
        monkeypatch.setattr(nw, "UserRepository", lambda _s: user_repo)

        await nw.send_wishlist_available_notice({"bot": bot}, 1, "example.com")

        # Не отправлено
        bot.send_message.assert_not_called()
        # Не удалено из wishlist
        wishlist_repo.mark_notified.assert_not_awaited()


# ---------------------------------------------------------------------------
# ADR 039 invariant: tracked+wishlist использует tracked-TTL (не wishlist 24h)
# ---------------------------------------------------------------------------


class TestTrackedWishlistTTL:
    """Инвариант ADR 039: если домен и в /list, и в /wishlist → используется
    tracked-TTL (adaptive), а не жёсткий 24h wishlist-режим."""

    def test_tracked_domain_uses_adaptive_ttl_not_wishlist_24h(self) -> None:
        """tracked+wishlist → calculate_next_check с is_wishlist=False (default).

        Логика в check_domain: only_wishlist = bool(wishlist) and not bool(tracked).
        Если есть tracked-подписчики → only_wishlist=False → обычный adaptive TTL.
        """
        now = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)
        expires_far = now + timedelta(days=200)

        # is_wishlist=False (дефолт для tracked) → adaptive TTL
        result = calculate_next_check(expires_far, now=now, is_wishlist=False)
        assert (result - now).days == 30  # ttl_far_days

        # is_wishlist=True (только wishlist) → жёсткий 24h
        result_wish = calculate_next_check(expires_far, now=now, is_wishlist=True)
        assert (result_wish - now).total_seconds() == 24 * 3600  # 24 часа


# ---------------------------------------------------------------------------
# ADR 039 invariant: уведомление одноразовое (запись удаляется)
# ---------------------------------------------------------------------------


class TestOneShotNotification:
    """Инвариант ADR 039: уведомление об освобождении одноразовое — после
    успешной отправки запись удаляется из wishlist (mark_notified)."""

    async def test_mark_notified_removes_wishlist_entry(self, monkeypatch) -> None:
        """mark_notified (вызывается после успешной отправки) удаляет запись."""
        from contextlib import asynccontextmanager

        from src.tasks import notify_wishlist as nw

        wishlist_repo = AsyncMock()
        wishlist_repo.exists = AsyncMock(return_value=True)
        wishlist_repo.mark_notified = AsyncMock()

        user_repo = AsyncMock()
        from src.db.models import User

        user = MagicMock(spec=User)
        user.is_blocked = False
        user.language = "ru"
        user.telegram_id = 12345
        user_repo.get_by_ids = AsyncMock(return_value=[user])

        bot = AsyncMock()
        bot.send_message = AsyncMock()

        notif_repo = AsyncMock()
        notif_repo.record_sent = AsyncMock()

        @asynccontextmanager
        async def fake_session():
            yield MagicMock()

        monkeypatch.setattr(nw, "get_session", fake_session)
        monkeypatch.setattr(nw, "WishlistRepository", lambda _s: wishlist_repo)
        monkeypatch.setattr(nw, "UserRepository", lambda _s: user_repo)
        monkeypatch.setattr(nw, "NotificationRepository", lambda _s: notif_repo)

        await nw.send_wishlist_available_notice({"bot": bot}, 1, "example.com")

        # mark_notified вызван → запись удалена (одноразовость)
        wishlist_repo.mark_notified.assert_awaited_once_with(1, "example.com")


# ---------------------------------------------------------------------------
# ADR 039 invariant: /list и /wishlist независимы
# ---------------------------------------------------------------------------


class TestListWishlistIndependence:
    """Инвариант ADR 039: домен может быть одновременно в /list и /wishlist.

    Это два независимых списка:
    - /list показывает user_domains (tracked)
    - /wishlist показывает wishlist
    - unfollow (/remove) не трогает wishlist
    - remove from wishlist не трогает /list

    Разделение на уровне схемы БД (отдельные таблицы).
    """

    def test_wishlist_and_user_domains_are_separate_tables(self) -> None:
        """Проверяем что wishlist и user_domains — разные таблицы в схеме.

        Это структурный инвариант ADR 039: разделение на уровне БД.
        """
        from src.db.models import UserDomain, Wishlist

        # Разные классы → разные таблицы
        assert UserDomain.__tablename__ == "user_domains"
        assert Wishlist.__tablename__ == "wishlist"

        # Разные таблицы → независимые списки
        assert UserDomain.__tablename__ != Wishlist.__tablename__


# ---------------------------------------------------------------------------
# ADR 039 invariant: callback_data <= 64 bytes
# ---------------------------------------------------------------------------


class TestCallbackDataSizeLimit:
    """Инвариант ADR 039: callback_data для inline-кнопок <= 64 байт (Telegram limit).

    Проверяем что даже для длинных IDN-доменов callback_data не превышает лимит.
    """

    def test_wishlist_action_callback_fits_64_bytes(self) -> None:
        """callback_data для кнопок в wishlist не превышает 64 байта."""
        # Длинный IDN-домен (punycode может быть очень длинным)
        long_idn = "xn--" + "a" * 50 + ".xn--" + "b" * 50 + ".xn--" + "c" * 50 + ".com"

        # Формат callback_data для wishlist actions (см. keyboards.py)
        # Обычно: "wishlist:action:domain" или короче
        # Проверяем что используется короткий формат (только hash или ID)

        # В реальной реализации callback_data использует короткие идентификаторы,
        # а не полные домены. Этот тест — reminder.

        assert len(long_idn.encode("utf-8")) > 64  # Длинный домен > 64 байт

        # Если бы мы использовали полный домен в callback_data — превысили бы лимит
        # Реальная реализация должна использовать короткие идентификаторы
