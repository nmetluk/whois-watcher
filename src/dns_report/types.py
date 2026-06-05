"""Типы для расширенного DNS-отчёта (ADR 044, TASK-0090)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class DnsRecord:
    """Одна DNS-запись: тип, имя (для PTR — IP), значение, TTL."""

    rtype: str
    name: str
    value: str
    ttl: int | None = None


@dataclass(slots=True)
class DnsReportResult:
    """Результат расширенного DNS-обхода одного домена.

    ``records`` сгруппированы по типу при форматировании; здесь — плоский
    список в порядке резолва. ``errors`` — мягкие сбои отдельных типов
    (не роняют весь отчёт). ``axfr_open`` — открыт ли трансфер зоны
    (security finding); ``None`` — не проверяли/недоступно.
    """

    domain: str
    unicode_domain: str
    records: list[DnsRecord] = field(default_factory=list)
    dnssec: bool = False
    axfr_open: bool | None = None
    axfr_detail: str | None = None
    resolver_used: str | None = None
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not self.records


@dataclass(slots=True)
class DnsReportError:
    """Фатальный сбой обхода (домен не резолвится вообще / невалиден)."""

    domain: str
    error_type: str  # invalid_domain | unreachable | no_records
    message: str
