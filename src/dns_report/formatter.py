"""Форматирование DNS-отчёта в текстовый файл (ADR 044, TASK-0090).

Простой текст (не HTML): отдаётся как ``.txt``-документ, поэтому не зависит
от локалей шаблонов — заголовки секций двуязычны минимально. Группировка
по типам записей в порядке, удобном для анализа.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.dns_report.types import DnsReportResult

# Порядок секций в отчёте (профессиональная логика: зона → делегирование →
# адреса → почта → политики → безопасность).
SECTION_ORDER = (
    "SOA",
    "NS",
    "A",
    "AAAA",
    "PTR",
    "CNAME",
    "MX",
    "SRV",
    "TXT",
    "CAA",
    "DNSKEY",
    "DS",
)

_SECTION_TITLE = {
    "SOA": "SOA — Start of Authority",
    "NS": "NS — Nameservers (делегирование)",
    "A": "A — IPv4",
    "AAAA": "AAAA — IPv6",
    "PTR": "PTR — обратные записи (reverse)",
    "CNAME": "CNAME — алиасы",
    "MX": "MX — почтовые серверы",
    "SRV": "SRV — сервисы",
    "TXT": "TXT — текстовые (SPF/DKIM/верификации)",
    "CAA": "CAA — выпуск сертификатов",
    "DNSKEY": "DNSKEY — ключи DNSSEC",
    "DS": "DS — delegation signer",
}


def _ttl(ttl: int | None) -> str:
    return f"ttl={ttl}" if ttl is not None else "ttl=?"


def format_dns_report(result: DnsReportResult) -> str:
    """Собрать текстовый отчёт. Чистая функция — удобно тестировать."""
    now = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("  DNS REPORT / DNS-ОТЧЁТ")
    lines.append(f"  Домен:    {result.unicode_domain}")
    if result.unicode_domain != result.domain:
        lines.append(f"  ASCII:    {result.domain}")
    lines.append(f"  Собрано:  {now}")
    lines.append(f"  Резолвер: {result.resolver_used or 'system'}")
    lines.append(f"  DNSSEC:   {'да (есть DNSKEY/DS)' if result.dnssec else 'нет'}")
    if result.axfr_open is True:
        lines.append(f"  AXFR:     ⚠ ОТКРЫТ ТРАНСФЕР ЗОНЫ — {result.axfr_detail}")
    elif result.axfr_open is False:
        lines.append("  AXFR:     закрыт (ок)")
    else:
        lines.append("  AXFR:     не проверялся")
    lines.append("=" * 60)
    lines.append("")

    # Группировка
    by_type: dict[str, list] = {}
    for rec in result.records:
        by_type.setdefault(rec.rtype, []).append(rec)

    total = 0
    for rtype in SECTION_ORDER:
        recs = by_type.get(rtype)
        if not recs:
            continue
        lines.append(f"── {_SECTION_TITLE.get(rtype, rtype)} ({len(recs)}) " + "─" * 6)
        for rec in recs:
            total += 1
            if rtype == "PTR":
                lines.append(f"  {rec.name:<40} → {rec.value}")
            else:
                lines.append(f"  {rec.value}    [{_ttl(rec.ttl)}]")
        lines.append("")

    # Типы, которых не нашлось (полезно аналитику — явно «нет», а не «забыли»)
    missing = [t for t in SECTION_ORDER if t not in by_type and t not in ("PTR", "DNSKEY", "DS")]
    if missing:
        lines.append("── Не найдено записей типов " + "─" * 6)
        lines.append("  " + ", ".join(missing))
        lines.append("")

    if result.errors:
        lines.append("── Ошибки резолва (частичные) " + "─" * 6)
        for rtype, err in result.errors.items():
            lines.append(f"  {rtype}: {err}")
        lines.append("")

    lines.append("─" * 60)
    lines.append(f"Всего записей: {total}")
    lines.append("Инструмент: Whois Watcher — бесплатный мониторинг доменов.")
    return "\n".join(lines)


__all__ = ["SECTION_ORDER", "format_dns_report"]
