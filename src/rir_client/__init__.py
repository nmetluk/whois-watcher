"""Universal HTTP client for rir2localdb API (ADR 031).

Async typed lookup of IP allocations and ASN information from the local
rir2localdb service (separate project, listens on
``host.docker.internal:18000`` via compose extra_hosts pattern — see ADR 028).

Public API:

- ``lookup_ip(addr, *, include_rpsl=True)`` → ``IPAllocation | RIRError``
- ``lookup_asn(num, *, include_rpsl=True)`` → ``ASNAllocation | RIRError``
- ``healthcheck()`` → ``bool`` (raises ``RIRUnreachable`` on network failure)
- ``get_status()`` → ``RIRStatus`` (raises ``RIRUnreachable``)

Two-tier error model: ``lookup_*`` return ``RIRError`` (no exceptions)
for predictable pattern matching in callers. ``healthcheck`` /
``get_status`` raise ``RIRUnreachable`` for use in cron tasks where
exception flow is idiomatic.
"""

from src.rir_client.client import (
    get_status,
    healthcheck,
    lookup_asn,
    lookup_ip,
)
from src.rir_client.errors import RIRError, RIRUnreachable
from src.rir_client.types import (
    ASNAllocation,
    IPAllocation,
    RIRStatus,
    Source,
    SyncRun,
)

__all__ = [
    "ASNAllocation",
    "IPAllocation",
    "RIRError",
    "RIRStatus",
    "RIRUnreachable",
    "Source",
    "SyncRun",
    "get_status",
    "healthcheck",
    "lookup_asn",
    "lookup_ip",
]
