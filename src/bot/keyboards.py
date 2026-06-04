"""Inline-клавиатуры и CallbackData-фабрики.

Все клавиатуры собираются здесь, чтобы:

- не дублировать логику в хэндлерах
- callback_data была типизирована через ``CallbackData`` aiogram 3.x —
  парсинг в хэндлерах через ``Filter`` фабрики, а не сырыми строками

Каждая фабрика возвращает готовый ``InlineKeyboardMarkup``. Локализованные
надписи берутся через ``t(key, lang)``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.locales import t
from src.utils.domains import registrable_domain

if TYPE_CHECKING:
    from src.db.models import UserDomain

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

    action: str  # follow | unfollow | refresh | raw | wishlist | unwishlist (ADR 039)
    domain: str


class WishlistAction(CallbackData, prefix="wish"):
    """Кнопки в уведомлении «домен освободился» (Этап 9)."""

    action: str  # "track" | "dismiss"
    domain: str


class NotifyConfig(CallbackData, prefix="ncfg"):
    """Кнопки inline-конфигуратора уведомлений (Этап 11, ADR 029).

    ``action``:
      - ``open`` — открыть конфигуратор (из карточки /whois / списка)
      - ``toggle`` — переключить ``field`` (notify_*) на противоположное
      - ``mute_toggle`` — переключить ``is_muted``
      - ``edit_days`` — запустить FSM редактирования notify_days
      - ``reset_days`` — сбросить override в NULL (использовать user-level)
      - ``close`` — убрать клавиатуру (для inline-embedded use-cases)

    ``domain`` — punycode-имя. ``field`` — имя поля в БД для action=toggle
    (``notify_expiry``, ``notify_registrar_change``, ...).

    callback_data Telegram режет до 64 байт; поэтому ``field`` опционален
    и используется только в toggle-action.
    """

    action: str
    domain: str
    field: str = ""


class ListPage(CallbackData, prefix="list"):
    """Пагинация и общие кнопки списка ``/list``."""

    action: str  # "prev" | "next" | "filter" | "csv"
    page: int = 0


class ListFilter(CallbackData, prefix="lfilter"):
    """Выбор фильтра из подменю списка."""

    name: str  # all | expiring | no_data | muted | critical | expired | wishlist


class ListSearch(CallbackData, prefix="lsearch"):
    """Кнопки поиска в ``/list`` (Этап 9).

    - ``open`` — переключает в FSM ``ListSearchStates.waiting_for_query``
    - ``clear`` — сбрасывает текущий поиск, остаётся текущий фильтр
    """

    action: str  # "open" | "clear"


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


class CmdArgCallback(CallbackData, prefix="cmdarg"):
    """Подтверждение «выполнить /<cmd> <domain>?» в FSM-flow (ADR 033).

    ``token`` — короткий идентификатор (uuid hex[:8]), по которому в
    FSM-data ищется ``(cmd, domain)``. В callback_data сам домен не
    кладём — лимит Telegram 64 байта не выдержит длинный IDN.
    """

    action: str  # "yes" | "no"
    token: str


class NotifyAction(CallbackData, prefix="notif"):
    """Действия из карточек уведомлений (Этап 5).

    - ``refresh`` — принудительная WHOIS-проверка домена (используется в
      «Уже продлил» и «Попробовать сейчас»).
    - ``mute``    — выключить все 4 типа уведомлений для домена (ADR 015).
    - ``enable``  — обратное к ``mute``: вернуть дефолтные флаги.
    """

    action: str  # "refresh" | "mute" | "enable"
    domain: str


class SubdomainAction(CallbackData, prefix="sub"):
    """Кнопки выбора поддоменов для отслеживания (ADR 037).

    - ``track`` — отслеживать конкретный поддомен (идёт в /add)
    - ``track_all`` — отслеживать все найденные поддомены
    - ``refresh`` — обновить список (запустить новый check_subdomains)

    ``idx`` — индекс поддомена в cached.subdomains (для action="track").
    Telegram режет callback_data до 64 байт, поэтому pack'им idx, не полный FQDN.
    """

    action: str  # "track" | "track_all" | "refresh"
    registrable: str  # registrable-домен
    idx: int = -1  # индекс поддомена в cached.subdomains (для action="track")


# ---------------------------------------------------------------------------
# Готовые клавиатуры
# ---------------------------------------------------------------------------


def start_keyboard(lang: str, *, webapp_url: str | None = None) -> InlineKeyboardMarkup:
    """Приветственное меню.

    :param webapp_url: публичный URL mini-app (``Settings.webapp_url``);
        если задан — добавляется кнопка запуска WebApp (нативный
        ``WebAppInfo``: открывается внутри клиента Telegram и передаёт
        ``initData`` автоматически, ADR 043).
    """
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
    if webapp_url:
        builder.button(
            text=t("button.webapp", lang),
            web_app=WebAppInfo(url=webapp_url),
        )
    builder.adjust(1)
    return builder.as_markup()


def webapp_open_keyboard(lang: str, webapp_url: str) -> InlineKeyboardMarkup:
    """Одна кнопка запуска WebApp — для команд ``/webapp`` / ``/app`` / ``/dashboard``."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t("button.webapp", lang),
        web_app=WebAppInfo(url=webapp_url),
    )
    builder.adjust(1)
    return builder.as_markup()


def whois_actions(
    domain: str,
    *,
    is_tracked: bool,
    is_wishlisted: bool = False,
    lang: str,
    show_wishlist: bool = True,
) -> InlineKeyboardMarkup:
    """Кнопки под карточкой ``/whois``.

    ``show_wishlist`` (Этап 9) — выводить ли кнопки wishlist.
    По умолчанию ``True``; хэндлер может скрыть в спец-случаях.

    ``is_wishlisted`` (ADR 039) — если True, показывает кнопку «убрать
    из wishlist», иначе — «добавить в wishlist».

    Кнопка «⚙️ Уведомления» (Этап 11) показывается только если домен
    отслеживается (``is_tracked=True``) — для нетрекаемых доменов
    конфигурировать нечего.
    """
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
    # TASK-0042 (ADR 040): reuse /subdomains enumeration from the card
    # TASK-0048: для subdomains/deep_email в callback кладём registrable (короче + семантично),
    # чтобы не превышать 64 байта Telegram на длинных FQDN (карточка поддомена).
    # Хэндлеры idempotent (registrable от registrable = сам).
    reg = registrable_domain(domain) or domain
    builder.button(
        text=t("button.subdomains", lang),
        callback_data=WhoisAction(action="subdomains", domain=reg).pack(),
    )
    # TASK-0041 (ADR 040): on-demand deep email (SPF/MTA-STS/DANE/BIMI)
    builder.button(
        text=t("button.deep_email", lang),
        callback_data=WhoisAction(action="deep_email", domain=reg).pack(),
    )
    if is_tracked:
        builder.button(
            text=t("notify_config.button", lang),
            callback_data=NotifyConfig(action="open", domain=domain).pack(),
        )
    if show_wishlist:
        if is_wishlisted:
            builder.button(
                text=t("button.wishlist_remove", lang),
                callback_data=WhoisAction(action="unwishlist", domain=domain).pack(),
            )
        else:
            builder.button(
                text=t("button.wishlist_add", lang),
                callback_data=WhoisAction(action="wishlist", domain=domain).pack(),
            )
    # Раскладка: первая кнопка (follow/unfollow) одна, потом по 2 в ряд.
    rows: list[int] = [1]
    extras = 4  # refresh + raw + subdomains + deep_email (TASK-0041/0042)
    if is_tracked:
        extras += 1
    if show_wishlist:
        extras += 1
    while extras > 0:
        take = 2 if extras >= 2 else 1
        rows.append(take)
        extras -= take
    builder.adjust(*rows)
    return builder.as_markup()


def notify_config_keyboard(
    user_domain: UserDomain,
    *,
    lang: str,
) -> InlineKeyboardMarkup:
    """Inline-конфигуратор уведомлений (Этап 11, ADR 029).

    7 переключателей по одной кнопке на ряд (легче тапать на мобиле).
    Каждая кнопка показывает текущее состояние (✅/❌); тап — toggle и
    перерисовка клавиатуры через ``edit_message_reply_markup``.
    """
    builder = InlineKeyboardBuilder()
    on = t("notify_config.toggle.on", lang)
    off = t("notify_config.toggle.off", lang)
    domain = user_domain.domain

    builder.row(
        InlineKeyboardButton(
            text=t("notify_config.edit_days", lang),
            callback_data=NotifyConfig(action="edit_days", domain=domain).pack(),
        )
    )
    # ADR 030: отдельная кнопка для SSL-дней — own override от WHOIS-days.
    builder.row(
        InlineKeyboardButton(
            text=t("notify_config.edit_ssl_days", lang),
            callback_data=NotifyConfig(action="edit_ssl_days", domain=domain).pack(),
        )
    )
    # TASK-0029, ADR 038: отдельная кнопка для интервала поддоменов.
    builder.row(
        InlineKeyboardButton(
            text=t("notify_config.edit_subdomain_interval", lang),
            callback_data=NotifyConfig(action="edit_subdomain_interval", domain=domain).pack(),
        )
    )
    for field, label_key in _TOGGLE_FIELDS:
        flag = bool(getattr(user_domain, field, False))
        prefix = on if flag else off
        builder.row(
            InlineKeyboardButton(
                text=f"{prefix} {t(label_key, lang)}",
                callback_data=NotifyConfig(action="toggle", domain=domain, field=field).pack(),
            )
        )
    is_muted = bool(getattr(user_domain, "is_muted", False))
    builder.row(
        InlineKeyboardButton(
            text=t(
                "notify_config.unmute_all" if is_muted else "notify_config.mute_all",
                lang,
            ),
            callback_data=NotifyConfig(action="mute_toggle", domain=domain).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=t("button.back", lang),
            callback_data=NotifyConfig(action="close", domain=domain).pack(),
        )
    )
    return builder.as_markup()


# (field-name в БД, ключ локали для подписи).
# Порядок отражает порядок в /whois карточке.
_TOGGLE_FIELDS: tuple[tuple[str, str], ...] = (
    ("notify_expiry", "notify_config.type.expiry"),
    ("notify_registrar_change", "notify_config.type.registrar_change"),
    ("notify_ns_change", "notify_config.type.ns_change"),
    ("notify_status_change", "notify_config.type.status_change"),
    ("notify_registrant_change", "notify_config.type.registrant_change"),
    ("notify_problem", "notify_config.type.problem"),
    # SSL (Этап 12, ADR 030)
    ("track_ssl", "notify_config.type.track_ssl"),
    ("notify_ssl_expiry", "notify_config.type.ssl_expiry"),
    ("notify_ssl_change_issuer", "notify_config.type.ssl_change_issuer"),
    # DNS (Этап 14, ADR 032)
    ("track_dns", "notify_config.type.track_dns"),
    ("notify_dns_a_change", "notify_config.type.dns_a_change"),
    ("notify_dns_aaaa_change", "notify_config.type.dns_aaaa_change"),
    ("notify_dns_ns_change", "notify_config.type.dns_ns_change"),
    ("notify_dns_unreachable", "notify_config.type.dns_unreachable"),
    # Email-intel (TASK-0018, ADR 036)
    ("track_email", "notify_config.type.track_email"),
    ("notify_email_change", "notify_config.type.email_change"),
    # Subdomain monitoring (TASK-0029, ADR 038)
    ("track_subdomains", "notify_config.type.track_subdomains"),
    ("notify_subdomain_new", "notify_config.type.subdomain_new"),
    ("notify_subdomain_removed", "notify_config.type.subdomain_removed"),
)


def wishlist_available_actions(domain: str, *, lang: str) -> InlineKeyboardMarkup:
    """Кнопки под уведомлением «домен освободился»."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t("notifications.wishlist.available.button_track", lang),
        callback_data=WishlistAction(action="track", domain=domain).pack(),
    )
    builder.button(
        text=t("notifications.wishlist.available.button_dismiss", lang),
        callback_data=WishlistAction(action="dismiss", domain=domain).pack(),
    )
    builder.adjust(1)
    return builder.as_markup()


def list_pagination(
    current_page: int,
    total_pages: int,
    *,
    lang: str,
    has_search: bool = False,
) -> InlineKeyboardMarkup:
    """Пагинация и кнопки списка ``/list``.

    Если ``has_search=True`` — добавляем кнопку «❌ Сбросить поиск».
    Иначе — обычная кнопка «🔍 Поиск».
    """
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
    if has_search:
        builder.row(
            InlineKeyboardButton(
                text=t("list.search.clear", lang),
                callback_data=ListSearch(action="clear").pack(),
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text=t("list.search.placeholder", lang),
                callback_data=ListSearch(action="open").pack(),
            )
        )
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
        ("critical", "list.filter.critical"),
        ("expired", "list.filter.expired"),
        ("no_data", "button.filter_no_data"),
        ("muted", "button.filter_muted"),
    ):
        builder.button(text=t(key, lang), callback_data=ListFilter(name=name).pack())
    builder.button(
        text=t("button.back", lang),
        callback_data=ListPage(action="prev", page=0).pack(),
    )
    builder.adjust(2)
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


def expiry_notification(domain: str, *, lang: str) -> InlineKeyboardMarkup:
    """Кнопки под напоминанием об истечении (Этап 5)."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t("notifications.expiry.button_renewed", lang),
        callback_data=NotifyAction(action="refresh", domain=domain).pack(),
    )
    builder.button(
        text=t("notifications.expiry.button_mute", lang),
        callback_data=NotifyAction(action="mute", domain=domain).pack(),
    )
    builder.adjust(1)
    return builder.as_markup()


def change_notification(domain: str, *, lang: str) -> InlineKeyboardMarkup:
    """Кнопка «Открыть домен» под уведомлением о смене данных."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t("notifications.change.button_open", lang),
        callback_data=NotifyAction(action="refresh", domain=domain).pack(),
    )
    return builder.as_markup()


def problem_notification(domain: str, *, lang: str) -> InlineKeyboardMarkup:
    """Кнопки под уведомлением о длительных проблемах с WHOIS."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t("notifications.problem.button_retry", lang),
        callback_data=NotifyAction(action="refresh", domain=domain).pack(),
    )
    builder.button(
        text=t("notifications.problem.button_mute", lang),
        callback_data=NotifyAction(action="mute", domain=domain).pack(),
    )
    builder.adjust(1)
    return builder.as_markup()


def ssl_expiry_notification(domain: str, *, lang: str) -> InlineKeyboardMarkup:
    """Кнопки под напоминанием об истечении SSL-сертификата (Этап 12)."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t("notifications.ssl_expiry.button_renewed", lang),
        callback_data=NotifyAction(action="refresh", domain=domain).pack(),
    )
    builder.button(
        text=t("notifications.ssl_expiry.button_mute", lang),
        callback_data=NotifyAction(action="mute", domain=domain).pack(),
    )
    builder.adjust(1)
    return builder.as_markup()


def cmd_arg_confirm_kb(token: str, *, lang: str) -> InlineKeyboardMarkup:
    """Кнопки «✅ Да / ❌ Нет» для FSM-flow подтверждения (ADR 033)."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t("commands.cmd_arg.yes", lang),
        callback_data=CmdArgCallback(action="yes", token=token).pack(),
    )
    builder.button(
        text=t("commands.cmd_arg.no", lang),
        callback_data=CmdArgCallback(action="no", token=token).pack(),
    )
    builder.adjust(2)
    return builder.as_markup()


def notify_enable_button(domain: str, *, lang: str) -> InlineKeyboardMarkup:
    """Кнопка «🔔 Включить обратно» под ответом на /unnotify."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t("button.notify_on", lang),
        callback_data=NotifyAction(action="enable", domain=domain).pack(),
    )
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


def subdomains_keyboard(
    registrable: str, subdomains: list[str], *, lang: str
) -> InlineKeyboardMarkup:
    """Клавиатура для списка поддоменов с кнопками opt-in (ADR 037).

    Для каждого поддомена — кнопка с именем поддомена.
    Внизу — «📌 Отслеживать все» и «🔄 Обновить».
    Telegram режет callback_data до 64 байт, поэтому pack'им idx, не полный FQDN.
    """
    from src.utils.idn import from_punycode

    builder = InlineKeyboardBuilder()

    # Кнопки по каждому поддомену (с именем поддомена)
    for idx, subdomain in enumerate(subdomains[:_MAX_SUBDOMAIN_BUTTONS]):
        display = from_punycode(subdomain)
        builder.button(
            text=f"📌 {display}",
            callback_data=SubdomainAction(
                action="track",
                registrable=registrable,
                idx=idx,
            ).pack(),
        )

    # Кнопка «Отслеживать все»
    builder.button(
        text=t("commands.subdomains.button_track_all", lang),
        callback_data=SubdomainAction(action="track_all", registrable=registrable).pack(),
    )

    # Кнопка «Обновить»
    builder.button(
        text=t("commands.subdomains.button_refresh", lang),
        callback_data=SubdomainAction(action="refresh", registrable=registrable).pack(),
    )

    # Раскладка: каждая кнопка track — одна, внизу 2 кнопки (track_all, refresh)
    shown = min(len(subdomains), _MAX_SUBDOMAIN_BUTTONS)
    builder.adjust(*([1] * shown + [2]))
    return builder.as_markup()


_MAX_SUBDOMAIN_BUTTONS = 50  # Лимит кнопок (Telegram restriction ~100 байт на callback)
