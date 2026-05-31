"""Тесты для notify_subdomain_changes (TASK-0033, ADR 038).

Полное покрытие fan-out логики (дедуп, mute, per-domain toggles, blocked,
обрезка 5+and_more, record_sent, TelegramForbiddenError → is_blocked).

Моки со spec=UserDomain / spec=User (anti-drift, см. CLAUDE.md).
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from src.db.models import User, UserDomain
from src.tasks import notify_subdomain_changes as nsc_mod


def _async_cm(value: object) -> MagicMock:
    """MagicMock acting as async context manager (for get_session)."""
    cm = MagicMock(name="session_cm")
    cm.__aenter__ = AsyncMock(return_value=value)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.fixture
def patches() -> Iterator[dict[str, MagicMock]]:
    """Patch get_session + repositories used inside notify_subdomain_changes.

    Also patch keyboard builder to keep test isolated from its impl.
    """
    with (
        patch.object(nsc_mod, "get_session") as gs,
        patch.object(nsc_mod, "DomainRepository") as dr_cls,
        patch.object(nsc_mod, "UserRepository") as ur_cls,
        patch.object(nsc_mod, "NotificationRepository") as nr_cls,
        patch.object(nsc_mod, "change_notification") as kb,
    ):
        session = MagicMock(name="session")
        gs.return_value = _async_cm(session)

        # Class mocks return the same instance mock on every instantiation
        # (DomainRepository(session), UserRepository(session), etc.)
        domain_repo = MagicMock(name="domain_repo")
        user_repo = MagicMock(name="user_repo")
        notif_repo = MagicMock(name="notif_repo")
        dr_cls.return_value = domain_repo
        ur_cls.return_value = user_repo
        nr_cls.return_value = notif_repo

        # Keyboard mock returns a dummy markup
        kb.return_value = MagicMock(name="reply_markup")

        yield {
            "session": session,
            "domain_repo": domain_repo,
            "user_repo": user_repo,
            "notif_repo": notif_repo,
            "keyboard": kb,
        }


def _ud(
    *,
    user_id: int = 42,
    is_muted: bool = False,
    notify_new: bool = True,
    notify_removed: bool = True,
) -> MagicMock:
    """UserDomain mock with spec (anti-drift)."""
    ud = MagicMock(spec=UserDomain)
    ud.user_id = user_id
    ud.is_muted = is_muted
    ud.notify_subdomain_new = notify_new
    ud.notify_subdomain_removed = notify_removed
    return ud


def _user(
    *,
    user_id: int = 42,
    blocked: bool = False,
    lang: str = "ru",
    tg_id: int = 123456789,
) -> MagicMock:
    """User mock with spec (anti-drift)."""
    u = MagicMock(spec=User)
    u.id = user_id
    u.is_blocked = blocked
    u.language = lang
    u.telegram_id = tg_id
    return u


def _ctx() -> dict[str, AsyncMock]:
    """Minimal ARQ ctx with bot mock."""
    return {"bot": AsyncMock(name="bot")}


class TestNotifySubdomainChangesEmptyAndEarlyReturn:
    """Ранние возвраты и базовые гарды."""

    @pytest.mark.asyncio
    async def test_empty_diff_returns_immediately(self, patches: dict[str, MagicMock]) -> None:
        """Пустой diff (оба списка пусты) — ранний return, без БД и без send."""
        bot = _ctx()["bot"]
        await nsc_mod.notify_subdomain_changes(
            {"bot": bot}, registrable_domain="example.com", diff={"new": [], "removed": []}
        )
        bot.send_message.assert_not_called()
        patches["domain_repo"].get_subscribers_by_registrable.assert_not_called()

    @pytest.mark.asyncio
    async def test_only_empty_new_and_removed_after_filter_still_skips(
        self, patches: dict[str, MagicMock]
    ) -> None:
        """Diff имеет данные, но у подписчика оба toggle=false → сообщение не шлём."""
        patches["domain_repo"].get_subscribers_by_registrable = AsyncMock(
            return_value=[_ud(notify_new=False, notify_removed=False)]
        )
        patches["user_repo"].get_by_ids = AsyncMock(return_value=[_user()])
        bot = _ctx()["bot"]

        await nsc_mod.notify_subdomain_changes(
            {"bot": bot},
            registrable_domain="example.com",
            diff={"new": ["a.example.com"], "removed": ["b.example.com"]},
        )
        bot.send_message.assert_not_called()
        patches["notif_repo"].record_sent.assert_not_called()


class TestNotifySubdomainChangesDedupAndMute:
    """Дедуп по user_id и is_muted kill-switch."""

    @pytest.mark.asyncio
    async def test_two_rows_same_user_dedups_to_one_message(
        self, patches: dict[str, MagicMock]
    ) -> None:
        """Два UserDomain одной user_id (apex + www) → ровно один send_message."""
        ud1 = _ud(user_id=7)
        ud2 = _ud(user_id=7)  # второй row того же юзера
        patches["domain_repo"].get_subscribers_by_registrable = AsyncMock(return_value=[ud1, ud2])
        patches["user_repo"].get_by_ids = AsyncMock(return_value=[_user(user_id=7, tg_id=999)])
        patches["notif_repo"].record_sent = AsyncMock(return_value=True)
        bot = _ctx()["bot"]

        await nsc_mod.notify_subdomain_changes(
            {"bot": bot},
            registrable_domain="example.com",
            diff={"new": ["www.example.com"], "removed": []},
        )

        bot.send_message.assert_awaited_once()
        assert bot.send_message.await_args.kwargs["chat_id"] == 999
        # record_sent только один раз (для new)
        patches["notif_repo"].record_sent.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_is_muted_skips_send_and_record(self, patches: dict[str, MagicMock]) -> None:
        """is_muted=True → пропуск, send не вызывается."""
        patches["domain_repo"].get_subscribers_by_registrable = AsyncMock(
            return_value=[_ud(is_muted=True)]
        )
        bot = _ctx()["bot"]

        await nsc_mod.notify_subdomain_changes(
            {"bot": bot},
            registrable_domain="example.com",
            diff={"new": ["x.example.com"], "removed": []},
        )
        bot.send_message.assert_not_called()
        patches["user_repo"].get_by_ids.assert_not_called()
        patches["notif_repo"].record_sent.assert_not_called()


class TestNotifySubdomainChangesToggles:
    """Honoring notify_subdomain_new / notify_subdomain_removed по-отдельности."""

    @pytest.mark.asyncio
    async def test_new_only_toggle_produces_only_new_section(
        self, patches: dict[str, MagicMock]
    ) -> None:
        """notify_new=True, notify_removed=False → в тексте только new_header, нет removed."""
        patches["domain_repo"].get_subscribers_by_registrable = AsyncMock(
            return_value=[_ud(notify_new=True, notify_removed=False)]
        )
        patches["user_repo"].get_by_ids = AsyncMock(return_value=[_user(lang="ru")])
        patches["notif_repo"].record_sent = AsyncMock(return_value=True)
        bot = _ctx()["bot"]

        await nsc_mod.notify_subdomain_changes(
            {"bot": bot},
            registrable_domain="example.com",
            diff={"new": ["a.example.com", "b.example.com"], "removed": ["old.example.com"]},
        )

        text = bot.send_message.await_args.kwargs["text"]
        assert "🆕 Обнаружены новые поддомены:" in text
        assert "➖ Исчезли поддомены:" not in text
        # record только для new
        patches["notif_repo"].record_sent.assert_awaited_with(
            user_id=42, domain="example.com", notification_type="subdomain_new"
        )

    @pytest.mark.asyncio
    async def test_removed_only_toggle_produces_only_removed_section(
        self, patches: dict[str, MagicMock]
    ) -> None:
        """notify_removed=True, notify_new=False → только removed-секция."""
        patches["domain_repo"].get_subscribers_by_registrable = AsyncMock(
            return_value=[_ud(notify_new=False, notify_removed=True)]
        )
        patches["user_repo"].get_by_ids = AsyncMock(return_value=[_user(lang="en")])
        patches["notif_repo"].record_sent = AsyncMock(return_value=True)
        bot = _ctx()["bot"]

        await nsc_mod.notify_subdomain_changes(
            {"bot": bot},
            registrable_domain="example.com",
            diff={"new": ["new.example.com"], "removed": ["gone.example.com"]},
        )

        text = bot.send_message.await_args.kwargs["text"]
        assert "➖ Removed subdomains:" in text
        assert "🆕 New subdomains detected:" not in text
        patches["notif_repo"].record_sent.assert_awaited_with(
            user_id=42, domain="example.com", notification_type="subdomain_removed"
        )

    @pytest.mark.asyncio
    async def test_both_toggles_produce_both_sections_with_separator(
        self, patches: dict[str, MagicMock]
    ) -> None:
        """Оба toggle true → обе секции + пустая строка-разделитель между ними."""
        patches["domain_repo"].get_subscribers_by_registrable = AsyncMock(
            return_value=[_ud(notify_new=True, notify_removed=True)]
        )
        patches["user_repo"].get_by_ids = AsyncMock(return_value=[_user()])
        patches["notif_repo"].record_sent = AsyncMock(return_value=True)
        bot = _ctx()["bot"]

        await nsc_mod.notify_subdomain_changes(
            {"bot": bot},
            registrable_domain="example.com",
            diff={"new": ["n.example.com"], "removed": ["r.example.com"]},
        )

        text = bot.send_message.await_args.kwargs["text"]
        assert "🆕 Обнаружены новые поддомены:" in text
        assert "➖ Исчезли поддомены:" in text
        # Две записи в журнал (new + removed)
        assert patches["notif_repo"].record_sent.await_count == 2


class TestNotifySubdomainChangesBlockedAndErrors:
    """is_blocked, TelegramForbiddenError (mark + no record), BadRequest (silent)."""

    @pytest.mark.asyncio
    async def test_blocked_user_skipped(self, patches: dict[str, MagicMock]) -> None:
        """user.is_blocked=True → пропуск send и record."""
        patches["domain_repo"].get_subscribers_by_registrable = AsyncMock(return_value=[_ud()])
        patches["user_repo"].get_by_ids = AsyncMock(return_value=[_user(blocked=True)])
        bot = _ctx()["bot"]

        await nsc_mod.notify_subdomain_changes(
            {"bot": bot},
            registrable_domain="example.com",
            diff={"new": ["x.example.com"], "removed": []},
        )
        bot.send_message.assert_not_called()
        patches["notif_repo"].record_sent.assert_not_called()

    @pytest.mark.asyncio
    async def test_forbidden_error_marks_blocked_and_skips_record(
        self, patches: dict[str, MagicMock]
    ) -> None:
        """TelegramForbiddenError → update_settings(is_blocked=True), record НЕ вызывается."""
        patches["domain_repo"].get_subscribers_by_registrable = AsyncMock(
            return_value=[_ud(user_id=99)]
        )
        patches["user_repo"].get_by_ids = AsyncMock(return_value=[_user(user_id=99, tg_id=555)])
        patches["user_repo"].update_settings = AsyncMock()
        bot = _ctx()["bot"]
        bot.send_message = AsyncMock(
            side_effect=TelegramForbiddenError(method=MagicMock(), message="bot blocked by user")
        )

        await nsc_mod.notify_subdomain_changes(
            {"bot": bot},
            registrable_domain="example.com",
            diff={"new": ["x.example.com"], "removed": []},
        )

        patches["user_repo"].update_settings.assert_awaited_once_with(99, is_blocked=True)
        patches["notif_repo"].record_sent.assert_not_called()
        # notified_users не добавлен, но на этом юзере и так конец

    @pytest.mark.asyncio
    async def test_bad_request_is_silent_no_block_no_record(
        self, patches: dict[str, MagicMock]
    ) -> None:
        """TelegramBadRequest → лог, continue, без update blocked и без record."""
        patches["domain_repo"].get_subscribers_by_registrable = AsyncMock(return_value=[_ud()])
        patches["user_repo"].get_by_ids = AsyncMock(return_value=[_user()])
        patches["user_repo"].update_settings = AsyncMock()
        bot = _ctx()["bot"]
        bot.send_message = AsyncMock(
            side_effect=TelegramBadRequest(method=MagicMock(), message="bad request")
        )

        await nsc_mod.notify_subdomain_changes(
            {"bot": bot},
            registrable_domain="example.com",
            diff={"new": ["x.example.com"], "removed": []},
        )

        patches["user_repo"].update_settings.assert_not_called()
        patches["notif_repo"].record_sent.assert_not_called()


class TestNotifySubdomainChangesTruncationAndRecord:
    """Обрезка >5 + and_more, и корректные вызовы record_sent."""

    @pytest.mark.asyncio
    async def test_more_than_5_new_shows_5_plus_and_more(
        self, patches: dict[str, MagicMock]
    ) -> None:
        """6+ new → в тексте 5 имён + строка «… и ещё N шт.» (ru)."""
        patches["domain_repo"].get_subscribers_by_registrable = AsyncMock(
            return_value=[_ud(notify_new=True, notify_removed=False)]
        )
        patches["user_repo"].get_by_ids = AsyncMock(return_value=[_user(lang="ru")])
        patches["notif_repo"].record_sent = AsyncMock(return_value=True)
        bot = _ctx()["bot"]

        new_list = [f"s{i}.example.com" for i in range(1, 8)]  # 7 шт.
        await nsc_mod.notify_subdomain_changes(
            {"bot": bot},
            registrable_domain="example.com",
            diff={"new": new_list, "removed": []},
        )

        text = bot.send_message.await_args.kwargs["text"]
        # Первые 5
        assert "  🆕 s1.example.com" in text
        assert "  🆕 s5.example.com" in text
        # 6 и 7 не в явном виде
        assert "s6.example.com" not in text
        assert "s7.example.com" not in text
        # and_more
        assert "… и ещё 2 шт." in text
        patches["notif_repo"].record_sent.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_record_sent_called_only_for_enabled_sections(
        self, patches: dict[str, MagicMock]
    ) -> None:
        """У юзера только notify_new → record только 'subdomain_new', даже если removed в diff."""
        patches["domain_repo"].get_subscribers_by_registrable = AsyncMock(
            return_value=[_ud(notify_new=True, notify_removed=False)]
        )
        patches["user_repo"].get_by_ids = AsyncMock(return_value=[_user()])
        patches["notif_repo"].record_sent = AsyncMock(return_value=True)
        bot = _ctx()["bot"]

        await nsc_mod.notify_subdomain_changes(
            {"bot": bot},
            registrable_domain="example.com",
            diff={"new": ["n1.example.com"], "removed": ["r1.example.com"]},
        )

        # Ровно один вызов record_sent с типом new
        patches["notif_repo"].record_sent.assert_awaited_once_with(
            user_id=42, domain="example.com", notification_type="subdomain_new"
        )


class TestNotifySubdomainChangesAggregationAndNPlusOne:
    """Тесты агрегации toggle'ов и отсутствия N+1 (TASK-0035, ADR 038).

    Пользователь может иметь несколько UserDomain-строк по одному registrable
    (например apex + поддомен). Мы должны:
    - Сделать ровно один get_by_ids на всю рассылку.
    - Применять OR по notify_* и "any muted" семантику.
    - Выдавать одно сообщение с объединёнными секциями.
    """

    @pytest.mark.asyncio
    async def test_user_with_conflicting_rows_gets_both_sections(
        self, patches: dict[str, MagicMock]
    ) -> None:
        """У юзера две строки: одна хочет new, вторая — removed → одно сообщение с обеими секциями (OR)."""
        # Две строки одного пользователя (разные домены под одним registrable)
        row1 = _ud(user_id=77, notify_new=True, notify_removed=False)
        row2 = _ud(user_id=77, notify_new=False, notify_removed=True)
        patches["domain_repo"].get_subscribers_by_registrable = AsyncMock(return_value=[row1, row2])
        patches["user_repo"].get_by_ids = AsyncMock(return_value=[_user(user_id=77, tg_id=999)])
        patches["notif_repo"].record_sent = AsyncMock(return_value=True)
        bot = _ctx()["bot"]

        await nsc_mod.notify_subdomain_changes(
            {"bot": bot},
            registrable_domain="example.com",
            diff={"new": ["new.example.com"], "removed": ["old.example.com"]},
        )

        # Ровно одно сообщение
        bot.send_message.assert_awaited_once()
        text = bot.send_message.await_args.kwargs["text"]
        assert "🆕 Обнаружены новые поддомены:" in text
        assert "➖ Исчезли поддомены:" in text

        # Две записи в журнал (по агрегированным флагам)
        assert patches["notif_repo"].record_sent.await_count == 2

    @pytest.mark.asyncio
    async def test_exactly_one_get_by_ids_call_for_multiple_subscribers(
        self, patches: dict[str, MagicMock]
    ) -> None:
        """Несколько подписчиков (в т.ч. с несколькими строками) → ровно один get_by_ids."""
        # Два разных пользователя, один из них имеет две строки
        subs = [
            _ud(user_id=1),
            _ud(user_id=2),
            _ud(user_id=2),  # вторая строка второго пользователя
        ]
        patches["domain_repo"].get_subscribers_by_registrable = AsyncMock(return_value=subs)
        patches["user_repo"].get_by_ids = AsyncMock(
            return_value=[_user(user_id=1), _user(user_id=2)]
        )
        patches["notif_repo"].record_sent = AsyncMock(return_value=True)
        bot = _ctx()["bot"]

        await nsc_mod.notify_subdomain_changes(
            {"bot": bot},
            registrable_domain="example.com",
            diff={"new": ["x.example.com"], "removed": []},
        )

        # Ключевой анти-N+1 инвариант
        patches["user_repo"].get_by_ids.assert_awaited_once()
        # Вызвали с полным списком (порядок не важен для теста)
        called_ids = set(patches["user_repo"].get_by_ids.await_args[0][0])
        assert called_ids == {1, 2}


class TestNotifySubdomainChangesHtmlEscaping:
    """Defense-in-depth escaping (TASK-0037).

    Даже если данные приходят нормализованными, мы экранируем всё, что попадает в HTML.
    """

    @pytest.mark.asyncio
    async def test_subdomain_with_html_meta_is_escaped(self, patches: dict[str, MagicMock]) -> None:
        """Поддомен с HTML-метасимволами приходит экранированным в тексте."""
        malicious = "<b>x</b>.example.com<script>alert(1)</script>"
        patches["domain_repo"].get_subscribers_by_registrable = AsyncMock(return_value=[_ud()])
        patches["user_repo"].get_by_ids = AsyncMock(return_value=[_user()])
        patches["notif_repo"].record_sent = AsyncMock(return_value=True)
        bot = _ctx()["bot"]

        await nsc_mod.notify_subdomain_changes(
            {"bot": bot},
            registrable_domain="example.com",
            diff={"new": [malicious], "removed": []},
        )

        text = bot.send_message.await_args.kwargs["text"]
        # Должно быть экранировано, а не сырой HTML
        assert "&lt;b&gt;x&lt;/b&gt;.example.com&lt;script&gt;alert(1)&lt;/script&gt;" in text
        # Сырой тег не должен присутствовать
        assert "<b>x</b>" not in text
        assert "<script>" not in text
