"""Доменные типы DNS-подсистемы (Этап 14, ADR 032).

Резолвленные DNS-записи — ``DNSRecords``. Любая ошибка резолва —
``DNSError`` с категорией ``error_type``. Эти типы — единственный
контракт между клиентом (``client.resolve_records``) и тасками
(``tasks.check_dns`` и т.д.).

В отличие от SSL-подсистемы, у DNS нет понятия "сертификат" —
мы возвращаем массивы A/AAAA/NS-записей напрямую. ``resolution_state``
различает три валидных результата: записи есть (``resolved``), есть
только MX без A/AAAA (``mx_only``), записей нет (``no_dns``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# Категории ошибок резолва.
DNSErrorType = Literal[
    "invalid_domain",  # idna нормализация упала
    "nxdomain",  # домен не существует
    "no_records",  # домен есть, но ни A/AAAA/NS/MX
    "timeout",  # все резолверы тайм-аут
    "servfail",  # резолвер вернул SERVFAIL
    "resolver_unreachable",  # все резолверы недостижимы
    "disabled",  # DNS_ENABLED=false (kill-switch)
    "internal_error",
]


# Тип резолюции при успехе. NB: даже при no_dns is_reachable=True
# (домен существует, просто без A/AAAA/MX) — это не ошибка резолва.
ResolutionState = Literal["resolved", "mx_only", "no_dns"]


@dataclass(slots=True, kw_only=True)
class DNSRecords:
    """Результат успешного DNS-резолва.

    ``resolution_state``:
    - ``resolved`` — есть хотя бы один A или AAAA
    - ``mx_only`` — нет A/AAAA, но есть MX (типичный parked /
      email-only домен)
    - ``no_dns`` — никаких записей вообще, но домен существует
    """

    domain: str
    is_reachable: bool

    a_records: list[str] = field(default_factory=list)
    aaaa_records: list[str] = field(default_factory=list)
    ns_records: list[str] = field(default_factory=list)

    resolution_state: ResolutionState = "resolved"

    # Какой резолвер реально ответил (из цепочки)
    resolver_used: str | None = None


@dataclass(slots=True, kw_only=True)
class DNSError:
    """Описание неудачной попытки резолва."""

    domain: str
    error_type: DNSErrorType
    message: str


DNSResult = DNSRecords | DNSError


__all__ = [
    "DNSError",
    "DNSErrorType",
    "DNSRecords",
    "DNSResult",
    "ResolutionState",
]
