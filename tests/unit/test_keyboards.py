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
        # 3 ряда по 1 кнопке (см. adjust(1))
        assert len(kb.inline_keyboard) == 3
        assert all(len(row) == 1 for row in kb.inline_keyboard)

    def test_whois_actions_tracked_vs_untracked(self) -> None:
        tracked = whois_actions("example.com", is_tracked=True, lang="ru")
        untracked = whois_actions("example.com", is_tracked=False, lang="ru")
        # Первая кнопка меняется между «следить» и «снять».
        assert tracked.inline_keyboard[0][0].text != untracked.inline_keyboard[0][0].text

    def test_list_pagination_hides_prev_on_first_page(self) -> None:
        kb = list_pagination(0, 5, lang="ru")
        # Первый ряд: только «Вперёд» (на стр.0 нет «Назад»).
        # При totals=5 будет ряд навигации и ряд с filter/csv.
        assert len(kb.inline_keyboard) == 2
        assert len(kb.inline_keyboard[0]) == 1

    def test_list_pagination_hides_next_on_last_page(self) -> None:
        kb = list_pagination(4, 5, lang="ru")
        assert len(kb.inline_keyboard) == 2
        assert len(kb.inline_keyboard[0]) == 1

    def test_list_pagination_no_nav_when_single_page(self) -> None:
        kb = list_pagination(0, 1, lang="ru")
        # Один ряд (filter / csv), кнопок навигации нет.
        assert len(kb.inline_keyboard) == 1

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
