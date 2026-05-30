"""Email-intel подсистема (ADR 036).

Сбор и парсинг email/policy записей (MX/SPF/DKIM/DMARC) для доменов.
Параллельная подсистема к WHOIS/SSL/DNS со своим кэшем и scheduler'ом.
"""

from src.email_intel.types import (
    DKIMInfo,
    DMARCPolicy,
    DMARCRecord,
    EmailIntelError,
    EmailIntelErrorType,
    EmailIntelResult,
    EmailIntelResultOrError,
    MXRecord,
    SPFMode,
    SPFRecord,
)

__all__ = [
    "MXRecord",
    "SPFRecord",
    "SPFMode",
    "DMARCPolicy",
    "DMARCRecord",
    "DKIMInfo",
    "EmailIntelResult",
    "EmailIntelError",
    "EmailIntelErrorType",
    "EmailIntelResultOrError",
]
