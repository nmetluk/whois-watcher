"""DNS resolver factory + классификатор исключений для email/deep (TASK-0079).

Централизует:
- build_resolver(settings) — системный или с override dns_nameservers из настроек
- classify_dns_exc — отличать «записи нет» (NXDOMAIN/NoAnswer) от «сбой резолва»
  (Timeout, NoNameservers, NoResolverConfiguration и т.п.)

Это решает баг: любой DNS-сбой молча трактовался как «MX нет» → is_reachable=True
с пустыми записями, и карточка показывала ложное «MX: не настроен».
"""

from __future__ import annotations

from typing import Literal

import dns.asyncresolver
import dns.exception
import dns.resolver

from src.config.settings import Settings, get_settings

# Таймауты DNS-резолва (seconds) — как в legacy client/deep_client
QUERY_TIMEOUT = 5
TOTAL_TIMEOUT = 10


def classify_dns_exc(exc: Exception) -> Literal["no_records", "unreachable"]:
    """Классифицирует DNSException: легитимное отсутствие записи vs недоступность.

    - no_records: NXDOMAIN (домен не существует) или NoAnswer (имя есть, но записей
      нужного типа нет) — валидно показывать «MX: не настроен» / пустой раздел.
    - unreachable: таймауты, отказы серверов имён, проблемы конфигурации резолвера,
      сетевые сбои — НЕЛЬЗЯ трактовать как «записей нет». Должно приводить к
      EmailIntelError(dns_unreachable) или logged warning в deep, чтобы в проде
      было видно реальную проблему (и не слать ложные «нет MX»).
    """
    # Явные типы из dnspython
    if isinstance(exc, dns.resolver.NXDOMAIN):
        return "no_records"
    if isinstance(exc, dns.resolver.NoAnswer):
        return "no_records"

    msg = str(exc).lower()
    if "nxdomain" in msg:
        return "no_records"

    # Сбои доступности / инфраструктуры
    if isinstance(exc, dns.resolver.LifetimeTimeout | dns.resolver.Timeout):
        return "unreachable"
    # dns.exception.Timeout тоже может приходить
    if isinstance(exc, dns.exception.Timeout):
        return "unreachable"

    if isinstance(exc, dns.resolver.NoNameservers):
        return "unreachable"

    if "no nameservers" in msg or "no resolver" in msg or "resolver configuration" in msg:
        return "unreachable"

    # Любой другой DNSException по умолчанию считаем недоступностью (defense-in-depth)
    if isinstance(exc, dns.exception.DNSException):
        return "unreachable"

    # Не-DNS — пусть вышестоящий обработчик решает, но для безопасности unreachable
    return "unreachable"


def build_resolver(settings: Settings | None = None) -> dns.asyncresolver.Resolver:
    """Фабрика async DNS resolver'а для email-intel и deep-коллекторов.

    - Всегда ставит timeout/lifetime (QUERY 5s / TOTAL 10s).
    - Если settings и settings.dns_nameservers непустой список — подставляет
      nameservers (override системного resolver'а в контейнере).
    - Пустой dns_nameservers (дефолт) → поведение как раньше (системный resolver).
    - Никогда не падает: при проблемах с get_settings возвращает дефолтный resolver.

    Используется в client.py (MX/TXT/DMARC/DKIM) и deep_client.py (SPF/MTA-STS/...).
    """
    if settings is None:
        try:
            settings = get_settings()
        except Exception:
            settings = None

    resolver = dns.asyncresolver.Resolver()
    resolver.timeout = QUERY_TIMEOUT
    resolver.lifetime = TOTAL_TIMEOUT

    if settings is not None:
        ns_list = getattr(settings, "dns_nameservers", None) or []
        if isinstance(ns_list, list | tuple):
            clean = [str(s).strip() for s in ns_list if str(s).strip()]
            if clean:
                resolver.nameservers = clean

    return resolver


__all__ = [
    "QUERY_TIMEOUT",
    "TOTAL_TIMEOUT",
    "classify_dns_exc",
    "build_resolver",
]
