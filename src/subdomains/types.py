"""Типы для subdomain enumeration (ADR 037)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubdomainEnumResult:
    """Результат enumeration через crt.sh.

    Attributes:
        registrable_domain: Registrable-домен (eTLD+1, ADR 035)
        subdomains: Список найденных поддоменов (нормализованных)
        is_reachable: True если crt.sh доступен, False при ошибке
        error: Текст ошибки (если был)
    """

    registrable_domain: str
    subdomains: list[str]
    is_reachable: bool
    error: str | None = None


@dataclass(frozen=True)
class SubdomainEnumError:
    """Ошибка enumeration (graceful degradation).

    Используется когда crt.sh недоступен/таймаут/rate-limit —
    не исключение, а результат-объект для consistent handling.

    Attributes:
        registrable_domain: Registrable-домен
        error_type: Тип ошибки (timeout, unavailable, rate_limit, parse_error)
        message: Человекочитаемое сообщение
    """

    registrable_domain: str
    error_type: str
    message: str


SubdomainEnumResultOrError = SubdomainEnumResult | SubdomainEnumError


__all__ = [
    "SubdomainEnumResult",
    "SubdomainEnumError",
    "SubdomainEnumResultOrError",
]
