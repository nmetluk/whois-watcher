"""Inline-клавиатуры и CallbackData-фабрики.

Все клавиатуры собираются здесь, чтобы:

- не дублировать логику в хэндлерах
- callback_data была типизирована через ``CallbackData`` aiogram 3.x —
  парсинг в хэндлерах через ``Filter`` фабрики, а не сырыми строками

Каждая фабрика возвращает готовый ``InlineKeyboardMarkup``. Локализованные
надписи берутся через ``t(key, lang)``.
"""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.locales import t

# ---------------------------------------------------------------------------
# CallbackData-фабрики
# ---------------------------------------------------------------------------


class StartAction(CallbackData, prefix="start"):
    """Кнопки приветственного экрана."""

    action: str  # "check" | "list" | "settings"


class WhoisAction(CallbackData, prefix="whois"):
    """Действия над доменом из карточки WHOIS.

    ``domain`` — punycode. Telegram режет callback_data до 64 байт, так что
    очень длинные домены придётся отдельно резать на стороне отправителя
    (для Этапа 2 это не критично — заглушки и так не используют).
    """

    action: str  # "follow" | "unfollow" | "refresh" | "raw"
    domain: str


class ListPage(CallbackData, prefix="list"):
    """Пагинация и общие кнопки списка ``/list``."""

    action: str  # "prev" | "next" | "filter" | "csv"
    page: int = 0


class ListFilter(CallbackData, prefix="lfilter"):
    """Выбор фильтра из подменю списка."""

    name: str  # "all" | "expiring" | "no_data" | "muted"


class SettingsAction(CallbackData, prefix="set"):
    """Главное меню ``/settings`` и подменю выбора пресетов."""

    action: str
    # дополнительный параметр (час 0–23, имя TZ, ключ пресета, ...)
    value: str = ""


class ConfirmAction(CallbackData, prefix="cfm"):
    """Подтверждение опасных действий (удаление и т. п.)."""

    action: str  # "delete_domain", ...
    target: str  # домен или иной id
    answer: str  # "yes" | "no"


class DownloadAction(CallbackData, prefix="dl"):
    """Кнопки превью импорта ``/download``."""

    action: str  # "add" | "cancel" | "show_invalid"


# ---------------------------------------------------------------------------
# Готовые клавиатуры
# ---------------------------------------------------------------------------


def start_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Приветственное меню."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t("button.check_domain", lang),
        callback_data=StartAction(action="check").pack(),
    )
    builder.button(
        text=t("button.my_domains", lang),
        callback_data=StartAction(action="list").pack(),
    )
    builder.button(
        text=t("button.settings", lang),
        callback_data=StartAction(action="settings").pack(),
    )
    builder.adjust(1)
    return builder.as_markup()


def whois_actions(domain: str, *, is_tracked: bool, lang: str) -> InlineKeyboardMarkup:
    """Кнопки под карточкой ``/whois``."""
    builder = InlineKeyboardBuilder()
    if is_tracked:
        builder.button(
            text=t("button.unfollow", lang),
            callback_data=WhoisAction(action="unfollow", domain=domain).pack(),
        )
    else:
        builder.button(
            text=t("button.follow", lang),
            callback_data=WhoisAction(action="follow", domain=domain).pack(),
        )
    builder.button(
        text=t("button.refresh", lang),
        callback_data=WhoisAction(action="refresh", domain=domain).pack(),
    )
    builder.button(
        text=t("button.raw", lang),
        callback_data=WhoisAction(action="raw", domain=domain).pack(),
    )
    builder.adjust(1, 2)
    return builder.as_markup()


def list_pagination(
    current_page: int,
    total_pages: int,
    *,
    lang: str,
) -> InlineKeyboardMarkup:
    """Пагинация и кнопки списка ``/list``."""
    builder = InlineKeyboardBuilder()
    nav: list[InlineKeyboardButton] = []
    if current_page > 0:
        nav.append(
            InlineKeyboardButton(
                text=t("button.list_prev", lang),
                callback_data=ListPage(action="prev", page=current_page - 1).pack(),
            )
        )
    if current_page < total_pages - 1:
        nav.append(
            InlineKeyboardButton(
                text=t("button.list_next", lang),
                callback_data=ListPage(action="next", page=current_page + 1).pack(),
            )
        )
    if nav:
        builder.row(*nav)
    builder.row(
        InlineKeyboardButton(
            text=t("button.list_filter", lang),
            callback_data=ListPage(action="filter", page=current_page).pack(),
        ),
        InlineKeyboardButton(
            text=t("button.list_csv", lang),
            callback_data=ListPage(action="csv", page=current_page).pack(),
        ),
    )
    return builder.as_markup()


def list_filters(lang: str) -> InlineKeyboardMarkup:
    """Подменю фильтров для ``/list``."""
    builder = InlineKeyboardBuilder()
    for name, key in (
        ("all", "button.filter_all"),
        ("expiring", "button.filter_expiring"),
        ("no_data", "button.filter_no_data"),
        ("muted", "button.filter_muted"),
    ):
        builder.button(text=t(key, lang), callback_data=ListFilter(name=name).pack())
    builder.button(
        text=t("button.back", lang),
        callback_data=ListPage(action="prev", page=0).pack(),
    )
    builder.adjust(1)
    return builder.as_markup()


def settings_main(lang: str) -> InlineKeyboardMarkup:
    """Главное меню ``/settings``."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t("button.settings_timezone", lang),
        callback_data=SettingsAction(action="tz").pack(),
    )
    builder.button(
        text=t("button.settings_time", lang),
        callback_data=SettingsAction(action="time").pack(),
    )
    builder.button(
        text=t("button.settings_days", lang),
        callback_data=SettingsAction(action="days").pack(),
    )
    builder.button(
        text=t("button.settings_language", lang),
        callback_data=SettingsAction(action="lang").pack(),
    )
    builder.adjust(2)
    return builder.as_markup()


# Популярные часовые пояса. Точный список можно расширять — главное, чтобы
# покрывал основную русскоязычную аудиторию (ADR 013) и крупные регионы.
POPULAR_TIMEZONES: tuple[str, ...] = (
    "Europe/Moscow",
    "Europe/Kaliningrad",
    "Europe/Kiev",
    "Europe/Minsk",
    "Asia/Almaty",
    "Asia/Yekaterinburg",
    "Asia/Novosibirsk",
    "Asia/Vladivostok",
    "Europe/London",
    "Europe/Berlin",
    "America/New_York",
    "America/Los_Angeles",
    "Asia/Tokyo",
    "Australia/Sydney",
)


def settings_timezone(lang: str) -> InlineKeyboardMarkup:
    """Подменю выбора часового пояса: пресеты + ручной ввод."""
    builder = InlineKeyboardBuilder()
    for tz_name in POPULAR_TIMEZONES:
        builder.button(
            text=tz_name,
            callback_data=SettingsAction(action="tz_pick", value=tz_name).pack(),
        )
    builder.button(
        text=t("button.tz_custom", lang),
        callback_data=SettingsAction(action="tz_custom").pack(),
    )
    builder.button(
        text=t("button.back", lang),
        callback_data=SettingsAction(action="back").pack(),
    )
    builder.adjust(2)
    return builder.as_markup()


def settings_time(lang: str) -> InlineKeyboardMarkup:
    """Подменю выбора часа отправки напоминаний (0–23)."""
    builder = InlineKeyboardBuilder()
    for hour in range(24):
        builder.button(
            text=f"{hour:02d}:00",
            callback_data=SettingsAction(action="time_pick", value=str(hour)).pack(),
        )
    builder.button(
        text=t("button.back", lang),
        callback_data=SettingsAction(action="back").pack(),
    )
    builder.adjust(4)
    return builder.as_markup()


def settings_days(lang: str) -> InlineKeyboardMarkup:
    """Подменю выбора дней напоминаний: пресеты + ручной ввод."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t("button.days_standard", lang),
        callback_data=SettingsAction(action="days_pick", value="30,7,1").pack(),
    )
    builder.button(
        text=t("button.days_often", lang),
        callback_data=SettingsAction(action="days_pick", value="60,30,14,7,3,1").pack(),
    )
    builder.button(
        text=t("button.days_last", lang),
        callback_data=SettingsAction(action="days_pick", value="1").pack(),
    )
    builder.button(
        text=t("button.days_custom", lang),
        callback_data=SettingsAction(action="days_custom").pack(),
    )
    builder.button(
        text=t("button.back", lang),
        callback_data=SettingsAction(action="back").pack(),
    )
    builder.adjust(1)
    return builder.as_markup()


def settings_language(lang: str) -> InlineKeyboardMarkup:
    """Подменю выбора языка."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t("button.lang_ru", lang),
        callback_data=SettingsAction(action="lang_pick", value="ru").pack(),
    )
    builder.button(
        text=t("button.lang_en", lang),
        callback_data=SettingsAction(action="lang_pick", value="en").pack(),
    )
    builder.button(
        text=t("button.back", lang),
        callback_data=SettingsAction(action="back").pack(),
    )
    builder.adjust(2, 1)
    return builder.as_markup()


def confirm_delete(domain: str, lang: str) -> InlineKeyboardMarkup:
    """Подтверждение удаления домена кнопкой из ``/list``."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t("button.confirm_yes", lang),
        callback_data=ConfirmAction(action="delete_domain", target=domain, answer="yes").pack(),
    )
    builder.button(
        text=t("button.confirm_no", lang),
        callback_data=ConfirmAction(action="delete_domain", target=domain, answer="no").pack(),
    )
    builder.adjust(2)
    return builder.as_markup()


def download_preview(new_count: int, *, has_invalid: bool, lang: str) -> InlineKeyboardMarkup:
    """Кнопки превью импорта ``/download``."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t("button.download_add", lang, count=new_count),
        callback_data=DownloadAction(action="add").pack(),
    )
    builder.button(
        text=t("button.cancel", lang),
        callback_data=DownloadAction(action="cancel").pack(),
    )
    if has_invalid:
        builder.button(
            text=t("button.download_show_invalid", lang),
            callback_data=DownloadAction(action="show_invalid").pack(),
        )
    builder.adjust(2, 1)
    return builder.as_markup()
