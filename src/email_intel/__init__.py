"""Email-intel подсистема (ADR 036 + ADR 040 deep).

Сбор и парсинг email/policy записей (MX/SPF/DKIM/DMARC) + deep (SPF recursion,
MTA-STS, TLS-RPT, DANE, BIMI) — on-demand коллекторы.
"""

from src.email_intel.deep_client import (
    fetch_bimi,
    fetch_dane,
    fetch_deep_email,
    fetch_mta_sts,
    fetch_tls_rpt,
)
from src.email_intel.deep_types import (
    BimiResult,
    DaneResult,
    DeepEmailError,
    DeepEmailErrorType,
    DeepEmailResult,
    DeepEmailResultOrError,
    MtaStsResult,
    SpfResolution,
    TlsRptResult,
)
from src.email_intel.spf_resolver import SPF_LOOKUP_LIMIT, resolve_spf
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
    # existing (ADR 036)
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
    # deep (ADR 040, TASK-0038)
    "SpfResolution",
    "MtaStsResult",
    "TlsRptResult",
    "DaneResult",
    "BimiResult",
    "DeepEmailResult",
    "DeepEmailError",
    "DeepEmailErrorType",
    "DeepEmailResultOrError",
    "resolve_spf",
    "SPF_LOOKUP_LIMIT",
    "fetch_deep_email",
    "fetch_mta_sts",
    "fetch_tls_rpt",
    "fetch_dane",
    "fetch_bimi",
]
