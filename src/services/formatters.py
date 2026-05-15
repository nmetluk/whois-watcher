"""Форматирование WHOIS-данных для UI: карточка ``/whois``, строка ``/list``,
блок «успех» для ``/add``.

Никаких побочных эффектов, никаких I/O — только текст. Все шаблоны живут
в локалях (``src.locales``), здесь только сборка.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime

from src.db.models import UserDomain, WhoisCache
from src.locales import t
from src.utils.formatting import format_date, format_days_until, get_expiry_emoji
from src.utils.idn import from_punycode
from src.whois.types import WhoisData


def _display_domain(domain_punycode: str) -> str:
    """Punycode → Unicode для отображения, плюс HTML-escape."""
    return html.escape(from_punycode(domain_punycode))


def _days_until_label(target: datetime, *, lang: str, now: datetime | None = None) -> str:
    """Возвращает «через N дней / истёк N дней назад / сегодня»."""
    _, text = format_days_until(target, lang=lang, now=now)
    return text


def format_whois_response(
    data: WhoisData,
    *,
    lang: str,
    fetched_at: datetime | None = None,
    now: datetime | None = None,
) -> str:
    """Полная карточка домена для ``/whois`` и ``/check``.

    ``fetched_at`` — момент последнего обновления данных (из ``whois_cache``).
    Если None — считаем, что fetched_at = now (т. е. показываем «только что»).
    """
    moment = now if now is not None else datetime.now(tz=UTC)
    display = _display_domain(data.domain)

    # Свободный домен — отдельный шаблон.
    if not data.is_registered:
        return t("commands.whois.free", lang, domain=display)

    sections: list[str] = [f"🌐 <b>{display}</b>", ""]

    expiry_lines = [t("commands.whois.section_expiry", lang)]
    if data.created_at is not None:
        expiry_lines.append(
            "├ "
            + t(
                "commands.whois.line_registered", lang, date=format_date(data.created_at, lang=lang)
            )
        )
    if data.expires_at is not None:
        days_text = _days_until_label(data.expires_at, lang=lang, now=moment)
        expiry_lines.append(
            "├ "
            + t(
                "commands.whois.line_expires",
                lang,
                date=format_date(data.expires_at, lang=lang),
                days_until=days_text,
            )
        )
    if data.updated_at is not None:
        expiry_lines.append(
            "└ "
            + t("commands.whois.line_updated", lang, date=format_date(data.updated_at, lang=lang))
        )
    # Преобразуем последний ├ в └ — это просто косметика «древа».
    expiry_lines = _fix_tree_endings(expiry_lines)
    if len(expiry_lines) > 1:
        sections.append("\n".join(expiry_lines))
        sections.append("")

    if data.registrar:
        sections.append(
            t("commands.whois.line_registrar", lang, registrar=html.escape(data.registrar))
        )
        sections.append("")

    if data.status:
        status_lines = [t("commands.whois.section_status", lang)]
        for item in data.status:
            status_lines.append(f"├ <code>{html.escape(item)}</code>")
        status_lines = _fix_tree_endings(status_lines)
        sections.append("\n".join(status_lines))
        sections.append("")

    if data.name_servers:
        ns_lines = [t("commands.whois.section_ns", lang)]
        for ns in data.name_servers:
            ns_lines.append(f"├ <code>{html.escape(ns)}</code>")
        ns_lines = _fix_tree_endings(ns_lines)
        sections.append("\n".join(ns_lines))
        sections.append("")

    # Источник данных.
    if fetched_at is None or _within_minutes(moment, fetched_at, minutes=2):
        sections.append(t("commands.whois.source_just_now", lang))
    else:
        ago = _days_until_label(fetched_at, lang=lang, now=moment)
        sections.append(t("commands.whois.source_cached", lang, ago=ago))

    return "\n".join(sections).rstrip()


def format_list_row(
    user_domain: UserDomain,
    cache: WhoisCache | None,
    *,
    lang: str,
    now: datetime | None = None,
) -> str:
    """Одна строка списка ``/list``: эмодзи + домен + дни до истечения + 🔕."""
    moment = now if now is not None else datetime.now(tz=UTC)
    muted = _is_muted(user_domain)
    muted_suffix = t("commands.list.muted_suffix", lang) if muted else ""
    display = _display_domain(user_domain.domain)

    if cache is None or cache.expires_at is None:
        emoji = get_expiry_emoji(None)
        return t(
            "commands.list.row_unknown",
            lang,
            emoji=emoji,
            domain=display,
            muted=muted_suffix,
        )
    days_left, days_text = format_days_until(cache.expires_at, lang=lang, now=moment)
    return t(
        "commands.list.row_known",
        lang,
        emoji=get_expiry_emoji(days_left),
        domain=display,
        days_until=days_text,
        date=format_date(cache.expires_at, lang=lang),
        muted=muted_suffix,
    )


def format_add_success(
    data: WhoisData,
    *,
    lang: str,
    notify_days_label: str,
) -> str:
    """Сообщение об успешном ``/add`` для домена, у которого уже есть WHOIS-данные."""
    display = _display_domain(data.domain)
    if data.expires_at is None:
        # Данные есть, но дата истечения не разобралась — показываем no_data текст.
        return t("commands.add.success_no_data", lang, domain=display)
    days_text = _days_until_label(data.expires_at, lang=lang)
    return t(
        "commands.add.success",
        lang,
        domain=display,
        expires=format_date(data.expires_at, lang=lang),
        days_left=days_text,
        registrar=html.escape(data.registrar) if data.registrar else "—",
        notify_days=notify_days_label,
    )


# ---------------------------------------------------------------------------
# Внутреннее
# ---------------------------------------------------------------------------


def _is_muted(domain: UserDomain) -> bool:
    """True, если все 4 типа уведомлений выключены."""
    return not (
        domain.notify_expiry
        or domain.notify_ns_change
        or domain.notify_registrar_change
        or domain.notify_status_change
    )


def _within_minutes(a: datetime, b: datetime, *, minutes: int) -> bool:
    return abs((a - b).total_seconds()) < minutes * 60


def _fix_tree_endings(lines: list[str]) -> list[str]:
    """Заменяет последний ``├`` на ``└`` — оформление «дерева» в RU/EN-шаблонах.

    Шаблоны мы пишем со всеми ``├``, чтобы не плодить варианты «последний/не
    последний» в локалях; правильное оформление концовки — здесь, динамически.
    """
    if len(lines) <= 1:
        return lines
    # Ищем последнюю строку, начинающуюся с ``├``, и меняем на ``└``.
    for i in range(len(lines) - 1, 0, -1):
        if lines[i].startswith("├ "):
            lines[i] = "└ " + lines[i][2:]
            return lines
    return lines
