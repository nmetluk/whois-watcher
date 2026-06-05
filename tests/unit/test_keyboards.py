"""Тесты ``src.bot.keyboards``: round-trip CallbackData и базовая структура."""

from __future__ import annotations

import pytest
from aiogram.filters.callback_data import CallbackData

from src.bot.keyboards import (
    POPULAR_TIMEZONES,
    ConfirmAction,
    DownloadAction,
    ListFilter,
    ListPage,
    SettingsAction,
    StartAction,
    WhoisAction,
    confirm_delete,
    download_preview,
    list_filters,
    list_pagination,
    settings_days,
    settings_language,
    settings_main,
    settings_time,
    settings_timezone,
    start_keyboard,
    webapp_open_keyboard,
    whois_actions,
)

# Все наши фабрики — для удобства параметризации round-trip теста.
_FACTORIES: tuple[tuple[type[CallbackData], dict[str, object]], ...] = (
    (StartAction, {"action": "check"}),
    (WhoisAction, {"action": "follow", "domain": "example.com"}),
    (ListPage, {"action": "next", "page": 3}),
    (ListFilter, {"name": "expiring"}),
    (SettingsAction, {"action": "tz_pick", "value": "Europe/Moscow"}),
    (ConfirmAction, {"action": "delete_domain", "target": "example.com", "answer": "yes"}),
    (DownloadAction, {"action": "add"}),
)


class TestCallbackDataRoundTrip:
    @pytest.mark.parametrize(("factory", "kwargs"), _FACTORIES)
    def test_pack_unpack(self, factory: type[CallbackData], kwargs: dict[str, object]) -> None:
        packed = factory(**kwargs).pack()
        unpacked = factory.unpack(packed)
        for key, value in kwargs.items():
            assert getattr(unpacked, key) == value

    def test_pack_under_telegram_limit(self) -> None:
        """callback_data ограничен 64 байтами Telegram-API.

        Берём «плохой» сценарий с длинным доменом — он должен влезть.
        """
        data = WhoisAction(action="refresh", domain="a" * 30 + ".com").pack()
        assert len(data.encode("utf-8")) <= 64


class TestKeyboards:
    def test_start_keyboard_has_three_buttons(self) -> None:
        kb = start_keyboard("ru")
        # 3 ряда по 1 кнопке (см. adjust(1)); без webapp_url кнопки WebApp нет
        assert len(kb.inline_keyboard) == 3
        assert all(len(row) == 1 for row in kb.inline_keyboard)
        assert all(row[0].web_app is None for row in kb.inline_keyboard)

    def test_start_keyboard_with_webapp_url_adds_button(self) -> None:
        """ADR 043: с webapp_url — 4-я кнопка с нативным WebAppInfo."""
        url = "https://bot.example.com/app/"
        kb = start_keyboard("ru", webapp_url=url)
        assert len(kb.inline_keyboard) == 4
        btn = kb.inline_keyboard[3][0]
        assert btn.web_app is not None
        assert btn.web_app.url == url
        assert btn.callback_data is None

    def test_webapp_open_keyboard(self) -> None:
        url = "https://bot.example.com/app/"
        kb = webapp_open_keyboard("en", url)
        assert len(kb.inline_keyboard) == 1
        assert kb.inline_keyboard[0][0].web_app is not None
        assert kb.inline_keyboard[0][0].web_app.url == url

    def test_whois_actions_tracked_vs_untracked(self) -> None:
        tracked = whois_actions("example.com", is_tracked=True, lang="ru")
        untracked = whois_actions("example.com", is_tracked=False, lang="ru")
        # Первая кнопка меняется между «следить» и «снять».
        assert tracked.inline_keyboard[0][0].text != untracked.inline_keyboard[0][0].text

    def test_list_pagination_hides_prev_on_first_page(self) -> None:
        kb = list_pagination(0, 5, lang="ru")
        # Этап 9: ряды → [nav], [search], [filter, csv].
        assert len(kb.inline_keyboard) == 3
        assert len(kb.inline_keyboard[0]) == 1  # только «Вперёд»

    def test_list_pagination_hides_next_on_last_page(self) -> None:
        kb = list_pagination(4, 5, lang="ru")
        assert len(kb.inline_keyboard) == 3
        assert len(kb.inline_keyboard[0]) == 1  # только «Назад»

    def test_list_pagination_no_nav_when_single_page(self) -> None:
        kb = list_pagination(0, 1, lang="ru")
        # Без навигации: [search], [filter, csv].
        assert len(kb.inline_keyboard) == 2

    def test_list_pagination_shows_clear_when_search_active(self) -> None:
        kb = list_pagination(0, 1, lang="ru", has_search=True)
        # has_search=True → первый ряд содержит «❌ Сбросить поиск».
        assert any("Сбросить" in btn.text for btn in kb.inline_keyboard[0])

    def test_settings_time_has_24_hours(self) -> None:
        kb = settings_time("ru")
        # Все часы 00–23 + кнопка «Назад».
        flat = [btn for row in kb.inline_keyboard for btn in row]
        assert sum(1 for btn in flat if btn.text.endswith(":00")) == 24

    def test_settings_timezone_includes_popular_list(self) -> None:
        kb = settings_timezone("ru")
        labels = {btn.text for row in kb.inline_keyboard for btn in row}
        for tz in POPULAR_TIMEZONES:
            assert tz in labels

    def test_other_keyboards_compose(self) -> None:
        # Smoke: ни одна фабрика не падает на сборке.
        for kb in (
            list_filters("ru"),
            settings_main("ru"),
            settings_days("ru"),
            settings_language("ru"),
            confirm_delete("example.com", "ru"),
            download_preview(42, has_invalid=True, lang="ru"),
            download_preview(0, has_invalid=False, lang="ru"),
        ):
            assert kb.inline_keyboard


class TestDnsReportButton:
    def test_whois_actions_includes_dns_report(self) -> None:
        from src.bot.keyboards import whois_actions

        kb = whois_actions("example.com", is_tracked=False, lang="ru")
        texts = [b.text for row in kb.inline_keyboard for b in row]
        assert any("DNS" in t for t in texts)

    def test_dns_report_callback_uses_dnsrep_action(self) -> None:
        from src.bot.keyboards import WhoisAction, whois_actions

        kb = whois_actions("example.com", is_tracked=False, lang="ru")
        cbs = [b.callback_data for row in kb.inline_keyboard for b in row if b.callback_data]
        dnsrep = [c for c in cbs if WhoisAction.unpack(c).action == "dnsrep"]
        assert len(dnsrep) == 1
        assert WhoisAction.unpack(dnsrep[0]).domain == "example.com"

    def test_dnsrep_not_longer_than_refresh(self) -> None:
        """dnsrep (6 симв.) ≤ refresh (7) — не двигает границу 64б callback."""
        from src.bot.keyboards import WhoisAction

        d = "a" * 30 + ".example.com"
        assert len(WhoisAction(action="dnsrep", domain=d).pack().encode()) <= len(
            WhoisAction(action="refresh", domain=d).pack().encode()
        )
