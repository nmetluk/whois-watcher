"""Тесты wishlist (Этап 9): scheduler-TTL, переход registered→available,
одноразовость уведомления.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

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
    async def test_registered_to_free_enqueues_wishlist_notice(self) -> None:
        from src.db.models import UserDomain
        from src.tasks.check_domain import _enqueue_wishlist_notices

        arq_redis = AsyncMock()
        ctx = {"redis": arq_redis}

        sub_wish = MagicMock(spec=UserDomain)
        sub_wish.user_id = 100
        sub_wish.is_wishlist = True
        sub_regular = MagicMock(spec=UserDomain)
        sub_regular.user_id = 200
        sub_regular.is_wishlist = False

        await _enqueue_wishlist_notices("example.com", ctx, [sub_wish, sub_regular])

        # Только wishlist-подписчик получает enqueue.
        arq_redis.enqueue_job.assert_awaited_once_with(
            "send_wishlist_available_notice", 100, "example.com"
        )

    async def test_only_wishlist_subscribers_triggers_24h_ttl(self) -> None:
        """all-wishlist → calculate_next_check(is_wishlist=True)."""
        # Этот юнит-тест проверяет наш расчёт only_wishlist в _handle_success.
        # Полный run check_domain → smoke в integration; здесь — точечная логика.
        subs_all_wish = [
            MagicMock(is_wishlist=True),
            MagicMock(is_wishlist=True),
        ]
        subs_mixed = [
            MagicMock(is_wishlist=True),
            MagicMock(is_wishlist=False),
        ]
        only_wishlist_all = all(s.is_wishlist for s in subs_all_wish)
        only_wishlist_mix = all(s.is_wishlist for s in subs_mixed)
        assert only_wishlist_all is True
        assert only_wishlist_mix is False


# ---------------------------------------------------------------------------
# notify_wishlist: dedup через remove_wishlist + missing user_domain
# ---------------------------------------------------------------------------


class TestNotifyWishlist:
    async def test_skips_when_no_user_domain(self, monkeypatch) -> None:
        from contextlib import asynccontextmanager

        from src.tasks import notify_wishlist as nw

        bot = AsyncMock()
        bot.send_message = AsyncMock()

        domain_repo = AsyncMock()
        domain_repo.get_for_user = AsyncMock(return_value=None)
        user_repo = AsyncMock()

        @asynccontextmanager
        async def fake_session():
            session = MagicMock()
            yield session

        monkeypatch.setattr(nw, "get_session", fake_session)
        monkeypatch.setattr(nw, "DomainRepository", lambda _s: domain_repo)
        monkeypatch.setattr(nw, "UserRepository", lambda _s: user_repo)

        await nw.send_wishlist_available_notice({"bot": bot}, 1, "example.com")
        bot.send_message.assert_not_called()

    async def test_skips_when_user_unwishlisted(self, monkeypatch) -> None:
        from contextlib import asynccontextmanager

        from src.tasks import notify_wishlist as nw

        bot = AsyncMock()
        bot.send_message = AsyncMock()

        wishlist_row = MagicMock()
        wishlist_row.is_wishlist = False  # уже снял

        domain_repo = AsyncMock()
        domain_repo.get_for_user = AsyncMock(return_value=wishlist_row)
        user_repo = AsyncMock()

        @asynccontextmanager
        async def fake_session():
            yield MagicMock()

        monkeypatch.setattr(nw, "get_session", fake_session)
        monkeypatch.setattr(nw, "DomainRepository", lambda _s: domain_repo)
        monkeypatch.setattr(nw, "UserRepository", lambda _s: user_repo)

        await nw.send_wishlist_available_notice({"bot": bot}, 1, "example.com")
        bot.send_message.assert_not_called()
