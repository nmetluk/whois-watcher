"""Форматирование WHOIS-данных для UI: карточка ``/whois``, строка ``/list``,
блок «успех» для ``/add``.

Никаких побочных эффектов, никаких I/O — только текст. Все шаблоны живут
в локалях (``src.locales``), здесь только сборка.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime

from src.db.models import (
    DNSCache,
    EmailDeepCache,
    EmailIntelCache,
    SSLCache,
    UserDomain,
    WhoisCache,
)
from src.dns_monitor import detect_ns_mismatch
from src.locales import t
from src.utils.domains import is_expiry_hidden_by_registry
from src.utils.formatting import format_date, format_days_until, get_expiry_emoji
from src.utils.idn import from_punycode
from src.whois.status_format import format_statuses
from src.whois.types import WhoisContact, WhoisData

# Усечение длинных списков IP — Cloudflare и другие CDN отдают 20+ адресов,
# карточка должна оставаться компактной.
_MAX_A_RECORDS_SHOWN = 5
_MAX_AAAA_RECORDS_SHOWN = 3


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
    elif is_expiry_hidden_by_registry(data.domain):
        # Registry policy (e.g. DENIC .de) — not missing data (TASK-0051)
        expiry_lines.append("├ " + t("commands.whois.line_expires_hidden", lang))
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

    owner_line = _format_owner_line(data.registrant, lang=lang)
    if owner_line is not None:
        sections.append(owner_line)
        sections.append("")

    if data.status:
        formatted = format_statuses(data.status, lang="en" if lang == "en" else "ru")
        if formatted:
            status_lines = [t("commands.whois.section_status", lang)]
            for item in formatted:
                status_lines.append(f"├ {item.emoji} {html.escape(item.text)}")
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
    """Одна строка списка ``/list``: эмодзи + домен + дни до истечения + 🔕.

    Wishlist (ADR 039) теперь в отдельной таблице — использует свой
    путь через WishlistRepository, не format_list_row.

    Поддомены (TASK-0005) помечаются значком `↳` и показывают родительский expiry.
    """
    moment = now if now is not None else datetime.now(tz=UTC)
    display = _display_domain(user_domain.domain)

    # Поддомен — добавляем значок ↳
    is_sub = getattr(user_domain, "is_subdomain", False)
    subdomain_mark = "↳ " if is_sub else ""

    muted = _is_muted(user_domain)
    muted_suffix = t("commands.list.muted_suffix", lang) if muted else ""

    if cache is None or cache.expires_at is None:
        if is_expiry_hidden_by_registry(user_domain.domain):
            # DENIC (.de) and similar — registry policy, not missing data (TASK-0051)
            emoji = "🔒"
            return t(
                "commands.list.row_expiry_hidden",
                lang,
                emoji=emoji,
                domain=display,
                muted=muted_suffix,
                subdomain_mark=subdomain_mark,
            )
        emoji = get_expiry_emoji(None)
        return t(
            "commands.list.row_unknown",
            lang,
            emoji=emoji,
            domain=display,
            muted=muted_suffix,
            subdomain_mark=subdomain_mark,
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
        subdomain_mark=subdomain_mark,
    )


def format_ssl_block(
    cache: SSLCache | None,
    *,
    lang: str,
    now: datetime | None = None,
) -> str | None:
    """SSL-блок для карточки ``/whois`` (Этап 12, ADR 030).

    Возвращает None, если данных нет или они нерелевантны (например,
    у домена нет HTTPS — это не повод что-то показывать в карточке).
    Иначе — компактный блок с датой истечения сертификата и издателем.
    """
    if cache is None or cache.last_checked_at is None:
        # Совсем ничего не проверяли — лучше не показывать, чем показать
        # бессмысленное «—».
        return None

    moment = now if now is not None else datetime.now(tz=UTC)

    # has_certificate=False + is_reachable=False/None — TLS не отвечает.
    if not cache.has_certificate:
        if cache.is_reachable is False:
            return t("commands.whois.ssl_unreachable", lang)
        return None  # не оставляли отметки — нечего показывать

    not_after = cache.not_after
    if not_after is None:
        return None

    days_left, days_text = format_days_until(not_after, lang=lang, now=moment)
    issuer = cache.issuer_o or cache.issuer_cn or "—"
    lines = [
        t("commands.whois.ssl_section", lang),
        "├ "
        + t(
            "commands.whois.ssl_line_expires",
            lang,
            date=format_date(not_after, lang=lang),
            days_until=days_text,
            emoji=get_expiry_emoji(days_left),
        ),
        "└ " + t("commands.whois.ssl_line_issuer", lang, issuer=html.escape(issuer)),
    ]
    return "\n".join(lines)


def _format_records_truncated(records: list[str], limit: int) -> str:
    """Усечение и HTML-escape списка IP/NS для строки карточки."""
    shown = records[:limit]
    text = ", ".join(html.escape(r) for r in shown)
    if len(records) > limit:
        text += f" (+{len(records) - limit})"
    return text


def format_dns_block(
    cache: DNSCache | None,
    *,
    whois_ns: list[str] | None,
    lang: str,
) -> str | None:
    """DNS-блок для карточки ``/whois`` (Этап 14, ADR 032).

    Возвращает ``None``, если данных нет (``last_checked_at is None``) или
    состояние ``resolution_state='unknown'``. Иначе — компактный блок:

    - ``resolved`` → tree-формат с A/AAAA/NS и подсветкой
      DNS-NS ↔ WHOIS-NS (🚨 на mismatch, ✓ на совпадение)
    - ``mx_only``/``no_dns`` → одна строка со статусом
    - ``error`` или ``is_reachable=False`` → "DNS не отвечает"

    ``whois_ns`` — список NS-серверов из ``whois_cache.name_servers``
    (для ``detect_ns_mismatch``). ``None`` если WHOIS не успел отработать.
    """
    if cache is None or cache.last_checked_at is None:
        return None

    state = cache.resolution_state

    if state == "unknown":
        return None

    if state == "error" or cache.is_reachable is False:
        return t("commands.whois.dns_unreachable", lang)

    if state == "mx_only":
        return t("commands.whois.dns_mx_only", lang)

    if state == "no_dns":
        return t("commands.whois.dns_no_dns", lang)

    # resolved — tree-формат. По контракту dns_monitor.types ``resolved`` =
    # хотя бы один A или AAAA, но ns_records может быть пустым.
    lines = [t("commands.whois.dns_section", lang)]

    if cache.a_records:
        records_text = _format_records_truncated(cache.a_records, _MAX_A_RECORDS_SHOWN)
        lines.append("├ " + t("commands.whois.dns_line_a", lang, records=records_text))

    if cache.aaaa_records:
        records_text = _format_records_truncated(cache.aaaa_records, _MAX_AAAA_RECORDS_SHOWN)
        lines.append("├ " + t("commands.whois.dns_line_aaaa", lang, records=records_text))

    if cache.ns_records:
        ns_text = ", ".join(html.escape(ns) for ns in cache.ns_records)
        mismatch = bool(whois_ns) and detect_ns_mismatch(cache.ns_records, whois_ns or [])
        if mismatch:
            lines.append("├ " + t("commands.whois.dns_line_ns_mismatch", lang, records=ns_text))
            registry_text = ", ".join(html.escape(n) for n in (whois_ns or []))
            lines.append(
                "└ " + t("commands.whois.dns_line_ns_registry", lang, records=registry_text)
            )
        else:
            lines.append("└ " + t("commands.whois.dns_line_ns_ok", lang, records=ns_text))
    elif len(lines) > 1 and lines[-1].startswith("├ "):
        # Нет NS — переоформим последнюю строку (A или AAAA) на закрывающий префикс.
        lines[-1] = "└ " + lines[-1][2:]

    if len(lines) == 1:
        # Заголовок без данных — лучше ничего не показывать.
        return None

    return "\n".join(lines)


def format_email_block(
    cache: EmailIntelCache | None,
    *,
    lang: str,
) -> str | None:
    """Email-intel блок для карточки ``/whois`` (TASK-0040, ADR 040).

    Компактная версия для инлайна:
    - MX (top-3 + счётчик остальных)
    - Одна строка статуса: SPF режим + DMARC policy

    Полный DKIM и детали — в кнопке «Глубокий e-mail» (TASK-0041).

    Возвращает ``None`` только для «ничего полезного» (unreachable и т.п.).
    Пустой/ещё не собранный кэш обрабатывается в хэндлере (pending placeholder).
    """
    if cache is None or cache.last_successful_check_at is None:
        return None

    if cache.is_reachable is False:
        return t("commands.whois.email_unreachable", lang)

    lines = [t("commands.whois.email_section", lang)]

    # MX (компактно, top-3)
    mx = cache.mx_records or []
    if mx:
        sorted_mx = sorted(mx, key=lambda r: r.get("priority", 0))
        shown = sorted_mx[:3]
        mx_hosts = ", ".join(html.escape(r.get("host", "")) for r in shown)
        if len(mx) > 3:
            mx_hosts += f" (+{len(mx) - 3})"
        lines.append("├ " + t("commands.whois.email_line_mx", lang, records=mx_hosts))
    else:
        lines.append("├ " + t("commands.whois.email_no_mx", lang))

    # Компактный статус: SPF + DMARC в одну строку (TASK-0040)
    spf_mode = cache.spf_mode or "none"
    mode_key = f"commands.whois.email_spf_mode.{spf_mode}"
    spf_text = t(mode_key, lang, default=spf_mode)

    if cache.dmarc_policy:
        dmarc_key = f"commands.whois.email_dmarc_policy.{cache.dmarc_policy}"
        dmarc_text = t(dmarc_key, lang, default=cache.dmarc_policy)
        if cache.dmarc_pct is not None and cache.dmarc_pct < 100:
            dmarc_text += f" {cache.dmarc_pct}%"
    else:
        # TASK-0048: dedicated compact key instead of fragile split on the full "DMARC: ..." string
        dmarc_text = t("commands.whois.email_dmarc_none_compact", lang, default="none")

    status_line = t("commands.whois.email_compact_status", lang, spf=spf_text, dmarc=dmarc_text)
    lines.append("└ " + status_line)

    return "\n".join(lines)


def format_pending_block(section: str, *, lang: str) -> str:
    """Общий плейсхолдер «⏳ Собираю …» для ещё не заполненного кэша.

    Используется для SSL/DNS/Email при первом /whois (или после refresh),
    когда мы только что заэнкьюили фоновую задачу. Пользователь видит
    явный хинт нажать «🔄 Обновить».
    """
    return t("commands.whois.pending_collect", lang, section=section)


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


def _format_owner_line(contact: WhoisContact | None, *, lang: str) -> str | None:
    """Возвращает готовую строку «👤 Владелец: …» или ``None`` если нечего показать.

    Логика:

    - есть organization → ``ООО "Пример" (RU)`` или без страны
    - нет org, но есть name → имя как organization
    - is_redacted И «Private Person» в name → ``Скрыт (физ.лицо)``
    - is_redacted без явного имени → ``Скрыт (приватность)``
    - совсем нет данных → секцию скрываем (возвращаем None)
    """
    if contact is None:
        return None

    if contact.organization:
        owner = (
            t(
                "commands.whois.owner_org",
                lang,
                org=html.escape(contact.organization),
                country=html.escape(contact.country),
            )
            if contact.country
            else t(
                "commands.whois.owner_org_no_country",
                lang,
                org=html.escape(contact.organization),
            )
        )
        return t("commands.whois.line_owner", lang, owner=owner)

    if contact.name and not contact.is_redacted:
        owner = (
            t(
                "commands.whois.owner_name",
                lang,
                name=html.escape(contact.name),
                country=html.escape(contact.country),
            )
            if contact.country
            else t(
                "commands.whois.owner_name_no_country",
                lang,
                name=html.escape(contact.name),
            )
        )
        return t("commands.whois.line_owner", lang, owner=owner)

    if contact.is_redacted:
        # «Private Person» в .ru / .su / .рф → подсказать что это физ.лицо.
        name_lower = (contact.name or "").lower().strip()
        if "private person" in name_lower:
            owner = t("commands.whois.owner_redacted_private", lang)
        else:
            owner = t("commands.whois.owner_redacted_privacy", lang)
        return t("commands.whois.line_owner", lang, owner=owner)

    return None


def _is_muted(domain: UserDomain) -> bool:
    """True если домен полностью замьючен через kill-switch (Этап 11).

    Раньше это вычислялось как «все 4 toggle'а выключены»; теперь
    ``UserDomain.is_muted`` — настоящее поле (ADR 029). При unmute
    индивидуальные настройки сохраняются.
    """
    return bool(getattr(domain, "is_muted", False))


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


# ---------------------------------------------------------------------------
# TASK-0041: Полный deep email разбор (on-demand)
# ---------------------------------------------------------------------------


def format_email_deep(
    cache: EmailDeepCache | None,
    *,
    lang: str,
) -> str:
    """Полный разбор deep email для кнопки «✉️ Глубокий e-mail» (TASK-0041, ADR 040).

    Десериализует данные из email_deep_cache (JSONB, сохранённые asdict'ами из
    DeepEmailResult) и рендерит читаемый отчёт с html.escape на всех значениях.
    """
    if cache is None:
        return t("deep_email.no_data", lang)

    display = _display_domain(cache.domain)
    lines: list[str] = [f"✉️ <b>{t('deep_email.header', lang, domain=display)}</b>", ""]

    # SPF
    if cache.spf:
        spf = cache.spf or {}
        sources: list[str] = spf.get("sources") or []
        lookup_count = spf.get("lookup_count", 0)
        exceeds = spf.get("exceeds_limit", False)

        spf_lines = [t("deep_email.section_spf", lang)]
        if sources:
            escaped = [html.escape(s) for s in sources[:8]]
            spf_lines.append("├ " + ", ".join(escaped))
            if len(sources) > 8:
                spf_lines.append(f"├ … (+{len(sources) - 8})")
        else:
            spf_lines.append("├ " + t("deep_email.spf_none", lang))

        exceeds_text = " ⚠️ " + t("deep_email.exceeds_limit", lang) if exceeds else ""
        spf_lines.append("└ " + t("deep_email.spf_stats", lang, count=lookup_count) + exceeds_text)
        spf_lines = _fix_tree_endings(spf_lines)
        lines.extend(spf_lines)
        lines.append("")

    # MTA-STS
    if cache.mta_sts:
        mta = cache.mta_sts or {}
        mta_lines = [t("deep_email.section_mta_sts", lang)]

        mode = mta.get("policy_mode") or "none"
        mta_lines.append("├ " + t("deep_email.mta_mode", lang, mode=html.escape(str(mode))))

        mx_list: list[str] = mta.get("mx") or []
        if mx_list:
            escaped = [html.escape(m) for m in mx_list[:5]]
            mta_lines.append("├ mx: " + ", ".join(escaped))
            if len(mx_list) > 5:
                mta_lines.append(f"├ … (+{len(mx_list) - 5})")

        max_age = mta.get("max_age")
        if max_age is not None:
            mta_lines.append("├ " + t("deep_email.mta_max_age", lang, seconds=max_age))

        reachable = bool(mta.get("reachable"))
        status = "✅" if reachable else "❌"
        mta_lines.append("└ " + f"{status} " + t("deep_email.mta_reachable", lang))

        mta_lines = _fix_tree_endings(mta_lines)
        lines.extend(mta_lines)
        lines.append("")

    # TLS-RPT
    if cache.tls_rpt:
        rpt = cache.tls_rpt or {}
        rpt_lines = [t("deep_email.section_tls_rpt", lang)]
        if rpt.get("present"):
            rua = rpt.get("rua")
            if rua:
                rpt_lines.append(
                    "└ " + t("deep_email.tls_rpt_rua", lang, rua=html.escape(str(rua)))
                )
            else:
                rpt_lines.append("└ " + t("deep_email.tls_rpt_present", lang))
        else:
            rpt_lines.append("└ " + t("deep_email.tls_rpt_none", lang))
        lines.extend(rpt_lines)
        lines.append("")

    # DANE per-MX
    if cache.dane:
        dane = cache.dane or {}
        host_tlsa: dict[str, bool] = dane.get("host_tlsa") or {}
        dane_lines = [t("deep_email.section_dane", lang)]

        if host_tlsa:
            items = list(host_tlsa.items())
            for idx, (host, has) in enumerate(items[:6]):
                prefix = "├ " if idx < len(items) - 1 else "└ "
                status = "✅ TLSA" if has else "∅ no TLSA"
                dane_lines.append(prefix + f"{html.escape(host)} — {status}")
            if len(items) > 6:
                dane_lines.append(f"└ … (+{len(items)-6})")
        else:
            dane_lines.append("└ " + t("deep_email.dane_none", lang))

        dane_lines = _fix_tree_endings(dane_lines)
        lines.extend(dane_lines)
        lines.append("")

    # BIMI
    if cache.bimi:
        bimi = cache.bimi or {}
        bimi_lines = [t("deep_email.section_bimi", lang)]
        if bimi.get("present"):
            logo = bimi.get("logo_url")
            vmc = bimi.get("vmc_url")
            if logo:
                bimi_lines.append("├ logo: " + html.escape(str(logo)))
            if vmc:
                bimi_lines.append("├ vmc: " + html.escape(str(vmc)))
            bimi_lines.append("└ " + t("deep_email.bimi_present", lang))
        else:
            bimi_lines.append("└ " + t("deep_email.bimi_none", lang))
        bimi_lines = _fix_tree_endings(bimi_lines)
        lines.extend(bimi_lines)

    # Footer
    fetched_at = getattr(cache, "fetched_at", None)
    if fetched_at is not None:
        lines.append("")
        lines.append(t("deep_email.fetched_at", lang, date=format_date(fetched_at, lang=lang)))

    return "\n".join(lines)
