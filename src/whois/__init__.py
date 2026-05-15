"""WHOIS / RDAP клиент: фасад, парсер, планировщик проверок.

Внешний интерфейс — ``lookup_domain`` из :mod:`src.whois.client`. Внутренние
модули (rdap, whois_protocol, parser) использовать напрямую только в тестах.
"""

from src.whois.client import lookup_domain, lookup_with_semaphore
from src.whois.diff import WhoisDiff, compute_diff
from src.whois.scheduler import calculate_next_check, calculate_retry_after_failure
from src.whois.types import WhoisData, WhoisError, WhoisResult

__all__ = [
    "WhoisData",
    "WhoisDiff",
    "WhoisError",
    "WhoisResult",
    "calculate_next_check",
    "calculate_retry_after_failure",
    "compute_diff",
    "lookup_domain",
    "lookup_with_semaphore",
]
