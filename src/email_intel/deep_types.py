"""Типы deep email (TASK-0038, ADR 040).

Расширенный почтовый разбор: SPF с рекурсией include/redirect,
MTA-STS, TLS-RPT, DANE/TLSA, BIMI.

Результаты — только по запросу (on-demand), без фонового мониторинга.
Все домены в punycode (нормализация на входе).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# Категории ошибок deep email collection (graceful degradation)
DeepEmailErrorType = Literal[
    "nxdomain",
    "timeout",
    "dns_error",
    "http_error",
    "parse_error",
    "internal_error",
]


@dataclass(slots=True, kw_only=True, frozen=True)
class SpfResolution:
    """Результат рекурсивного SPF-разбора (include: / redirect=).

    sources — итоговые авторизующие механизмы после разворачивания
    include/redirect (ip4:, ip6:, a:, mx:, ptr:, exists: и т.п. без include/redirect).
    lookup_count — число DNS TXT-запросов (включая рекурсивные).
    exceeds_limit — True если превышен лимит 10 lookups (RFC 7208 §4.6.4).
    """

    sources: list[str]
    lookup_count: int
    exceeds_limit: bool


@dataclass(slots=True, kw_only=True, frozen=True)
class MtaStsResult:
    """Результат MTA-STS (RFC 8461).

    txt_present — есть TXT _mta-sts.<domain>.
    policy_mode — enforce | testing | none (из policy файла).
    mx — список mx= из policy (может быть wildcard).
    max_age — max-age из policy (секунды).
    reachable — удалось ли успешно скачать policy по HTTPS (без редиректов).
    """

    txt_present: bool
    policy_mode: Literal["enforce", "testing", "none"] | None = None
    mx: list[str] = field(default_factory=list)
    max_age: int | None = None
    reachable: bool = False


@dataclass(slots=True, kw_only=True, frozen=True)
class TlsRptResult:
    """Результат TLS-RPT (RFC 8460)."""

    present: bool  # Есть TXT _smtp._tls.<domain>
    rua: str | None = None  # rua= reporting URI (mailto:... или https:...)


@dataclass(slots=True, kw_only=True, frozen=True)
class DaneResult:
    """DANE/TLSA для MX-хостов (порт 25, _25._tcp.<mx>).

    host_tlsa: {mx_host: has_tlsa_records}
    Отсутствие TLSA-записи для хоста — валидное состояние (False).
    """

    host_tlsa: dict[str, bool]


@dataclass(slots=True, kw_only=True, frozen=True)
class BimiResult:
    """BIMI (Brand Indicators for Message Identification).

    TXT default._bimi.<domain>.
    logo_url — l= (HTTPS URL логотипа SVG).
    vmc_url — a= (VMC certificate, optional).
    """

    present: bool
    logo_url: str | None = None
    vmc_url: str | None = None


@dataclass(slots=True, kw_only=True)
class DeepEmailResult:
    """Полный результат deep email сбора для домена (on-demand)."""

    domain: str
    is_reachable: bool  # True если хотя бы базовый DNS прошёл

    spf: SpfResolution | None = None
    mta_sts: MtaStsResult | None = None
    tls_rpt: TlsRptResult | None = None
    dane: DaneResult | None = None
    bimi: BimiResult | None = None


@dataclass(slots=True, kw_only=True)
class DeepEmailError:
    """Описание неудачной попытки deep email сбора."""

    domain: str
    error_type: DeepEmailErrorType
    message: str


DeepEmailResultOrError = DeepEmailResult | DeepEmailError


__all__ = [
    "DeepEmailErrorType",
    "SpfResolution",
    "MtaStsResult",
    "TlsRptResult",
    "DaneResult",
    "BimiResult",
    "DeepEmailResult",
    "DeepEmailError",
    "DeepEmailResultOrError",
]
