"""Форматирование «Полного ответа WHOIS» — текстового файла (Этап 8).

Раньше кнопка «Полный ответ» в карточке ``/whois`` отдавала либо
``raw_text`` (для WHOIS:43), либо ``str(dict)`` (для RDAP) — последний
вариант нечитаем (Python ``repr`` словаря).

Этот модуль строит текстовый файл с двумя разделами:

1. **Человекочитаемая шапка** — все ключевые секции (домен, сроки,
   регистратор, владелец, admin/tech/abuse, статусы, NS, DNSSEC) с
   локализованными названиями и переведёнными статусами.

2. **Сырые данные источника** — JSON pretty-print для RDAP, оригинальный
   текст для WHOIS:43. Это даёт пользователю и удобный обзор, и
   возможность проверить данные «как есть».

Без I/O. Возвращает ``str``; хэндлер ``_send_raw`` оборачивает в
``BufferedInputFile``.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from src.db.models import WhoisCache
from src.services.whois_facade import _cache_to_data
from src.utils.idn import from_punycode
from src.whois.status_format import format_statuses
from src.whois.types import WhoisContact, WhoisData

_BAR = "=" * 60


def format_whois_full_text(
    data: WhoisData,
    cache_row: WhoisCache,
    *,
    lang: Literal["ru", "en"] = "ru",
) -> str:
    """Собирает текстовый «Полный ответ» для отправки как ``.txt``.

    :param data: разобранные WHOIS-данные (после ``_cache_to_data``).
    :param cache_row: ORM-запись из ``whois_cache`` — нужна для metadata
        (``fetched_at``, ``raw_data``) и денормализованного abuse-email,
        если он там окажется.
    :param lang: язык переведённых меток статусов в секции Status. Заголовки
        секций оставлены на английском намеренно — это «техническая выгрузка»,
        часть пользователей шлёт файл в саппорт регистратора.
    """
    raw_data: dict[str, Any] = dict(cache_row.raw_data or {})
    is_rdap = _is_rdap_payload(raw_data)
    source_label = _source_label(raw_data, cache_row=cache_row, is_rdap=is_rdap)
    domain_pc = data.domain
    domain_unicode = from_punycode(domain_pc)

    lines: list[str] = []
    lines.append(_BAR)
    lines.append(f"WHOIS information for {domain_unicode}")
    lines.append(_BAR)
    lines.append(f"Source:    {source_label}")
    if cache_row.fetched_at is not None:
        lines.append(f"Retrieved: {_iso(cache_row.fetched_at)}")
    if cache_row.last_successful_fetch_at is not None and (
        cache_row.fetched_at is None or cache_row.last_successful_fetch_at != cache_row.fetched_at
    ):
        lines.append(f"Last OK:   {_iso(cache_row.last_successful_fetch_at)}")
    lines.append("")

    # ----- Domain -----
    lines.append("[Domain]")
    lines.append(f"  Name:           {domain_pc}")
    if domain_pc != domain_unicode:
        lines.append(f"  Unicode name:   {domain_unicode}")
    lines.append("")

    # ----- Registration timeline -----
    lines.append("[Registration timeline]")
    lines.append(f"  Created:        {_iso_or_dash(data.created_at)}")
    lines.append(f"  Updated:        {_iso_or_dash(data.updated_at)}")
    lines.append(f"  Expires:        {_iso_or_dash(data.expires_at)}")
    lines.append("")

    # ----- Registrar -----
    lines.append("[Registrar]")
    lines.append(f"  Name:           {data.registrar or '—'}")
    iana_id = _registrar_iana_id(raw_data)
    if iana_id:
        lines.append(f"  IANA ID:        {iana_id}")
    abuse_email = _abuse_email(data, raw_data)
    if abuse_email:
        lines.append(f"  Abuse contact:  {abuse_email}")
    lines.append("")

    # ----- Contacts: Registrant -----
    lines.append("[Registrant]")
    if data.registrant is not None:
        for line in _format_contact_lines(data.registrant):
            lines.append(f"  {line}")
    else:
        lines.append("  (not present in response)")
    lines.append("")

    # ----- Contacts: Admin -----
    if data.admin is not None:
        lines.append("[Admin Contact]")
        for line in _format_contact_lines(data.admin):
            lines.append(f"  {line}")
        lines.append("")

    # ----- Contacts: Tech -----
    if data.tech is not None:
        lines.append("[Tech Contact]")
        for line in _format_contact_lines(data.tech):
            lines.append(f"  {line}")
        lines.append("")

    # ----- Status -----
    lines.append("[Status]")
    if data.status:
        formatted = format_statuses(
            data.status,
            lang=lang if lang == "en" else "ru",
            drop_trivial_when_others_present=False,
        )
        for item in formatted:
            lines.append(f"  • {item.raw_code}")
            lines.append(f"      {item.emoji} {item.text}")
    else:
        lines.append("  —")
    lines.append("")

    # ----- Nameservers -----
    lines.append("[Nameservers]")
    if data.name_servers:
        for ns in data.name_servers:
            lines.append(f"  • {ns}")
    else:
        lines.append("  —")
    lines.append("")

    # ----- DNSSEC -----
    dnssec = _dnssec_status(raw_data)
    if dnssec is not None:
        lines.append("[DNSSEC]")
        lines.append(f"  Status: {dnssec}")
        lines.append("")

    # ----- Raw -----
    lines.append(_BAR)
    lines.append("Raw source data")
    lines.append(_BAR)
    lines.append(_format_raw_payload(raw_data, is_rdap=is_rdap))
    if not lines[-1].endswith("\n"):
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_rdap_payload(raw_data: dict[str, Any]) -> bool:
    """RDAP-payload не содержит ключа ``raw_text`` — это типовой
    маркер парсера ``parse_whois_text`` (см. parser.py).
    """
    if "raw_text" in raw_data:
        return False
    # Дополнительная страховка — наличие RDAP-specific ключей.
    return any(
        key in raw_data
        for key in ("objectClassName", "rdapConformance", "entities", "events", "ldhName")
    )


def _source_label(
    raw_data: dict[str, Any],
    *,
    cache_row: WhoisCache,
    is_rdap: bool,
) -> str:
    """«rdap (registrar URL)» / «whois (port 43, <server>)» — лучшее что есть."""
    del cache_row  # placeholder для возможного расширения позже
    if is_rdap:
        # Имя RDAP-сервера в links/self или в notices — слишком хрупко;
        # отдаём общее «rdap» без хвоста.
        return "rdap"
    return "whois (port 43)"


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _iso_or_dash(dt: datetime | None) -> str:
    return dt.isoformat() if dt is not None else "—"


def _format_contact_lines(contact: WhoisContact) -> list[str]:
    """Несколько ``Field: value`` строк для одного контакта.

    Пустые поля скрываем. ``is_redacted`` рендерим отдельной строкой
    ``Status: private/...`` чтобы читатель видел почему данных мало.
    """
    out: list[str] = []
    if contact.organization:
        out.append(f"Organization:   {contact.organization}")
    if contact.name:
        out.append(f"Name:           {contact.name}")
    if contact.country:
        out.append(f"Country:        {contact.country}")
    if contact.email:
        out.append(f"Email:          {contact.email}")
    if contact.phone:
        out.append(f"Phone:          {contact.phone}")
    if contact.is_redacted:
        out.append("Status:         private (registry redacted)")
    elif not out:
        # Все поля пустые и не redacted — необычная ситуация, но логируем,
        # чтоб не выводить пустую секцию.
        out.append("Status:         visible (no fields present)")
    else:
        out.insert(0, "Status:         visible")
    return out


def _registrar_iana_id(raw_data: dict[str, Any]) -> str | None:
    """Извлекает ``Registrar IANA ID`` из raw_data — для RDAP и WHOIS-текста."""
    # RDAP: entities[role=registrar].publicIds[type ~ "IANA"]
    entities = raw_data.get("entities")
    if isinstance(entities, list):
        for e in entities:
            if not isinstance(e, dict):
                continue
            roles = e.get("roles") or []
            if not isinstance(roles, list) or "registrar" not in roles:
                continue
            for pid in e.get("publicIds") or []:
                if not isinstance(pid, dict):
                    continue
                if "iana" in str(pid.get("type", "")).lower():
                    ident = pid.get("identifier")
                    if ident:
                        return str(ident)
    # WHOIS-текст: «Registrar IANA ID: 376»
    raw_text = raw_data.get("raw_text")
    if isinstance(raw_text, str):
        for line in raw_text.splitlines():
            if "registrar iana id" in line.lower():
                _, _, val = line.partition(":")
                val = val.strip()
                if val:
                    return val
    return None


def _abuse_email(data: WhoisData, raw_data: dict[str, Any]) -> str | None:
    """Берём abuse email из ``contacts`` (RDAP) или из raw_text WHOIS."""
    for c in data.contacts:
        if c.role == "abuse" and c.email:
            return c.email
    raw_text = raw_data.get("raw_text")
    if isinstance(raw_text, str):
        for line in raw_text.splitlines():
            if "registrar abuse contact email" in line.lower():
                _, _, val = line.partition(":")
                val = val.strip()
                if val:
                    return val
    return None


def _dnssec_status(raw_data: dict[str, Any]) -> str | None:
    """Извлекает DNSSEC-статус: RDAP secureDNS или WHOIS-текст «DNSSEC: ...»."""
    secure_dns = raw_data.get("secureDNS")
    if isinstance(secure_dns, dict):
        if secure_dns.get("delegationSigned"):
            return "signed"
        if "delegationSigned" in secure_dns:
            return "unsigned"
    raw_text = raw_data.get("raw_text")
    if isinstance(raw_text, str):
        for line in raw_text.splitlines():
            if line.strip().lower().startswith("dnssec"):
                _, _, val = line.partition(":")
                val = val.strip()
                if val:
                    return val
    return None


def _format_raw_payload(raw_data: dict[str, Any], *, is_rdap: bool) -> str:
    """RDAP → pretty-printed JSON. WHOIS-текст → как есть. Иначе fallback."""
    if not raw_data:
        return "(no raw payload stored)"
    if is_rdap:
        # Pretty JSON, без сортировки ключей — сохраняем порядок RDAP-сервера.
        return json.dumps(raw_data, indent=2, ensure_ascii=False)
    raw_text = raw_data.get("raw_text")
    if isinstance(raw_text, str):
        return raw_text
    return json.dumps(raw_data, indent=2, ensure_ascii=False)


def build_full_text_from_cache_row(
    cache_row: WhoisCache,
    *,
    lang: Literal["ru", "en"] = "ru",
) -> str:
    """Удобный обёрток для хэндлера: WhoisCache → готовый текст файла."""
    data = _cache_to_data(cache_row, cache_row.domain)
    return format_whois_full_text(data, cache_row, lang=lang)


__all__ = [
    "build_full_text_from_cache_row",
    "format_whois_full_text",
]
