"""Универсальный async DNS resolver с ASN-фильтрацией
(Этап 14, ADR 032).

Параллельная подсистема к ``whois/``, ``ssl/``, ``rir_client/``.
В v0.8.0 — chain external resolvers (Cloudflare 1.1.1.1 + Google
8.8.8.8). В v0.9 — локальный unbound на хосте по образцу ADR 028.

Public API:

- ``resolve_records(domain)`` → ``DNSResult`` (DNSRecords | DNSError)
- ``enrich_with_asn(ips)`` → ``list[int]`` (placeholder в v0.8.0)
- ``compute_dns_diff(old, new, new_asn_set)`` → ``DNSDiff``
- ``detect_ns_mismatch(dns_ns, whois_ns)`` → ``bool``
- ``calculate_next_dns_check(...)`` → ``datetime``
"""

from src.dns_monitor.asn_filter import enrich_with_asn
from src.dns_monitor.client import resolve_records
from src.dns_monitor.diff import DNSDiff, compute_dns_diff, detect_ns_mismatch
from src.dns_monitor.scheduler import calculate_next_dns_check
from src.dns_monitor.types import (
    DNSError,
    DNSErrorType,
    DNSRecords,
    DNSResult,
    ResolutionState,
)

__all__ = [
    "DNSDiff",
    "DNSError",
    "DNSErrorType",
    "DNSRecords",
    "DNSResult",
    "ResolutionState",
    "calculate_next_dns_check",
    "compute_dns_diff",
    "detect_ns_mismatch",
    "enrich_with_asn",
    "resolve_records",
]
