"""Доменные типы SSL-подсистемы (Этап 12, ADR 030).

Парсенный X.509-сертификат — ``SSLCertificate``. Любая ошибка
TLS-handshake / connection / parsing — ``SSLError`` с категорией
``error_type``. Эти типы — единственный контракт между клиентом
(``client.fetch_certificate``) и тасками (``tasks.check_ssl`` и т.д.).

Все datetime — timezone-aware UTC (cryptography ≥ 42 отдаёт
``not_valid_before_utc`` / ``not_valid_after_utc``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

# Категории ошибок. ``no_https`` — валидный «у сайта просто нет HTTPS»
# (не алерт), остальные — реальные сбои.
SSLErrorType = Literal[
    "connection_refused",
    "connection_timeout",
    "tls_handshake_failed",
    "no_https",
    "invalid_certificate",
    "internal_error",
]


@dataclass(slots=True, kw_only=True)
class SSLCertificate:
    """Парсенный X.509-сертификат, готовый к UPSERT в ``ssl_cache``."""

    domain: str
    is_reachable: bool
    has_certificate: bool

    not_before: datetime | None = None
    not_after: datetime | None = None

    issuer_cn: str | None = None
    issuer_o: str | None = None

    subject_cn: str | None = None
    subject_alt_names: list[str] = field(default_factory=list)

    serial_number: str | None = None
    fingerprint_sha256: str | None = None
    signature_algorithm: str | None = None


@dataclass(slots=True, kw_only=True)
class SSLError:
    """Описание неудачной попытки fetch-а SSL-сертификата."""

    domain: str
    error_type: SSLErrorType
    message: str


SSLResult = SSLCertificate | SSLError


__all__ = [
    "SSLCertificate",
    "SSLError",
    "SSLErrorType",
    "SSLResult",
]
