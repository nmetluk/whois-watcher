"""Async TLS-клиент для извлечения сертификата с :443 (Этап 12, ADR 030).

Без chain-validation (``CERT_NONE``) — нас интересует **сам peer cert**,
даже если он самоподписан / истёк / выдан недоверенным CA. Парсинг —
через cryptography. Все исключения превращаем в типизированный
``SSLError`` — caller (таски) не обрабатывает сетевую кухню.

Privacy: SSL-данные публичные (любой может их получить через тот же
TLS handshake), логируем спокойно.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import ssl as ssl_module

import idna
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.x509.oid import ExtensionOID, NameOID

from src.ssl.types import SSLCertificate, SSLError, SSLResult
from src.utils.idn import normalize_domain

logger = logging.getLogger(__name__)

DEFAULT_PORT = 443
CONNECT_TIMEOUT = 10  # seconds на TLS handshake


async def fetch_certificate(domain: str) -> SSLResult:
    """Открывает TCP+TLS к ``<domain>:443`` и возвращает peer cert.

    Возвращает либо ``SSLCertificate``, либо ``SSLError`` (с категорией).
    Никогда не бросает исключение.
    """
    try:
        normalized = normalize_domain(domain)
    except (idna.IDNAError, ValueError, UnicodeError) as exc:
        return SSLError(
            domain=domain,
            error_type="invalid_certificate",
            message=f"invalid domain syntax: {exc}",
        )

    # SSL-context без chain-validation: мы хотим прочитать ЛЮБОЙ
    # сертификат — даже истёкший, самоподписанный, с неверным CN.
    context = ssl_module.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl_module.CERT_NONE

    writer: asyncio.StreamWriter | None = None
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                normalized,
                DEFAULT_PORT,
                ssl=context,
                server_hostname=normalized,
            ),
            timeout=CONNECT_TIMEOUT,
        )
        del reader  # не читаем, только handshake
    except TimeoutError:
        return SSLError(
            domain=normalized,
            error_type="connection_timeout",
            message=f"TLS handshake timed out after {CONNECT_TIMEOUT}s",
        )
    except ConnectionRefusedError as exc:
        # Connection refused на :443 = у домена нет HTTPS-сервиса.
        # Семантически это no_https, а не «упал» — не алерт.
        return SSLError(
            domain=normalized,
            error_type="no_https",
            message=f"Port 443 closed: {exc}",
        )
    except ssl_module.SSLError as exc:
        return SSLError(
            domain=normalized,
            error_type="tls_handshake_failed",
            message=f"TLS handshake failed: {exc}",
        )
    except OSError as exc:
        # DNS-фейл / сеть недоступна / host без A-записей — у домена нет
        # HTTPS-эндпоинта, не повод для алерта (домен может быть зоной
        # email-only / parked / редиректом 80→404).
        msg = str(exc).lower()
        if (
            "unreachable" in msg
            or "no route" in msg
            or "name or service not known" in msg
            or "temporary failure in name resolution" in msg
            or "no address associated" in msg
            or "no such host" in msg
            or "nodename nor servname" in msg
        ):
            return SSLError(
                domain=normalized,
                error_type="no_https",
                message=f"Network/DNS unreachable: {exc}",
            )
        return SSLError(
            domain=normalized,
            error_type="connection_refused",
            message=f"Connection error: {exc}",
        )
    except Exception as exc:
        # Любое неожиданное — логируем и возвращаем internal_error.
        logger.warning("ssl fetch unexpected error for %s: %s", normalized, exc)
        return SSLError(
            domain=normalized,
            error_type="internal_error",
            message=f"Unexpected {type(exc).__name__}: {exc}",
        )

    assert writer is not None  # invariant: try-block выше его установил
    try:
        ssl_obj = writer.get_extra_info("ssl_object")
        if ssl_obj is None:
            return SSLError(
                domain=normalized,
                error_type="tls_handshake_failed",
                message="SSL object not available after handshake",
            )
        der_bytes = ssl_obj.getpeercert(binary_form=True)
        if not der_bytes:
            return SSLError(
                domain=normalized,
                error_type="invalid_certificate",
                message="Empty peer certificate",
            )
        return _parse_x509(normalized, der_bytes)
    except Exception as exc:
        logger.warning("ssl parse error for %s: %s", normalized, exc)
        return SSLError(
            domain=normalized,
            error_type="invalid_certificate",
            message=f"Failed to parse certificate: {exc}",
        )
    finally:
        if writer is not None:
            writer.close()
            # close может бросить ResourceWarning / OSError при уже
            # закрытом сокете — нам не важно.
            with contextlib.suppress(Exception):
                await writer.wait_closed()


def _parse_x509(domain: str, der_bytes: bytes) -> SSLCertificate:
    """Парсит DER-байты в ``SSLCertificate``."""
    cert = x509.load_der_x509_certificate(der_bytes)

    issuer_cn: str | None = None
    issuer_o: str | None = None
    for attr in cert.issuer:
        if attr.oid == NameOID.COMMON_NAME:
            issuer_cn = _attr_str(attr.value)
        elif attr.oid == NameOID.ORGANIZATION_NAME:
            issuer_o = _attr_str(attr.value)

    subject_cn: str | None = None
    for attr in cert.subject:
        if attr.oid == NameOID.COMMON_NAME:
            subject_cn = _attr_str(attr.value)
            break

    sans: list[str] = []
    try:
        san_ext = cert.extensions.get_extension_for_oid(
            ExtensionOID.SUBJECT_ALTERNATIVE_NAME
        )
        # ext.value — SubjectAlternativeName: знаем тип, но mypy видит
        # только ExtensionType-базу. Явный get_values_for_type обходит это.
        san_value = san_ext.value
        assert isinstance(san_value, x509.SubjectAlternativeName)
        sans = list(san_value.get_values_for_type(x509.DNSName))
    except x509.ExtensionNotFound:
        pass

    fingerprint = cert.fingerprint(hashes.SHA256()).hex()

    # signature_algorithm_oid имеет атрибут _name (внутренний, но
    # стабильный в cryptography 42+); fallback на dotted-id.
    sig_alg = getattr(cert.signature_algorithm_oid, "_name", None) or str(
        cert.signature_algorithm_oid.dotted_string
    )

    return SSLCertificate(
        domain=domain,
        is_reachable=True,
        has_certificate=True,
        not_before=cert.not_valid_before_utc,
        not_after=cert.not_valid_after_utc,
        issuer_cn=issuer_cn,
        issuer_o=issuer_o,
        subject_cn=subject_cn,
        subject_alt_names=sans,
        serial_number=str(cert.serial_number),
        fingerprint_sha256=fingerprint,
        signature_algorithm=sig_alg,
    )


def _attr_str(value: object) -> str | None:
    """cryptography может вернуть str или bytes для атрибутов имени."""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace") or None
        except Exception:
            return None
    if isinstance(value, str):
        return value or None
    return None


__all__ = ["CONNECT_TIMEOUT", "DEFAULT_PORT", "fetch_certificate"]
