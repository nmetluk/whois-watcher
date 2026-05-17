"""Тесты ``src.ssl.client``.

Сетевые операции (``asyncio.open_connection``) замокированы целиком —
проверяем классификацию ошибок и парсинг peer cert. Для парсинга
генерируем самоподписанный X.509 через ``cryptography`` — это даёт
честный DER на вход ``_parse_x509`` без походов в сеть.
"""

from __future__ import annotations

import asyncio
import socket
import ssl as ssl_module
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from src.ssl.client import _parse_x509, fetch_certificate
from src.ssl.types import SSLCertificate, SSLError

# ---------------------------------------------------------------------
# helpers — генерация валидного DER для теста парсера
# ---------------------------------------------------------------------


def _generate_self_signed(
    *,
    common_name: str = "example.com",
    issuer_org: str = "Test CA",
    sans: list[str] | None = None,
    days_valid: int = 90,
) -> bytes:
    """Возвращает DER самоподписанного сертификата для тестов парсинга."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, issuer_org),
        ]
    )
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(123456789)
        .not_valid_before(datetime(2026, 5, 1, tzinfo=UTC))
        .not_valid_after(datetime(2026, 5, 1, tzinfo=UTC) + timedelta(days=days_valid))
    )
    if sans:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.DNSName(name) for name in sans]),
            critical=False,
        )
    cert = builder.sign(private_key=key, algorithm=hashes.SHA256())
    return cert.public_bytes(serialization.Encoding.DER)


# ---------------------------------------------------------------------
# parsing — _parse_x509
# ---------------------------------------------------------------------


class TestParseX509:
    def test_basic_fields_extracted(self) -> None:
        der = _generate_self_signed(common_name="example.com", issuer_org="Test CA")
        cert = _parse_x509("example.com", der)

        assert isinstance(cert, SSLCertificate)
        assert cert.domain == "example.com"
        assert cert.is_reachable is True
        assert cert.has_certificate is True
        assert cert.subject_cn == "example.com"
        assert cert.issuer_cn == "example.com"  # self-signed
        assert cert.issuer_o == "Test CA"
        assert cert.not_before == datetime(2026, 5, 1, tzinfo=UTC)
        assert cert.not_after == datetime(2026, 5, 1, tzinfo=UTC) + timedelta(days=90)
        assert cert.serial_number == "123456789"
        assert cert.fingerprint_sha256 is not None
        # SHA-256 hex = 64 символа
        assert len(cert.fingerprint_sha256) == 64
        assert all(c in "0123456789abcdef" for c in cert.fingerprint_sha256)
        assert cert.signature_algorithm  # «sha256WithRSAEncryption» или OID
        assert "sha256" in cert.signature_algorithm.lower()

    def test_subject_alt_names_extracted(self) -> None:
        der = _generate_self_signed(
            sans=["example.com", "www.example.com", "api.example.com"]
        )
        cert = _parse_x509("example.com", der)
        assert cert.subject_alt_names == [
            "example.com",
            "www.example.com",
            "api.example.com",
        ]

    def test_no_sans_returns_empty_list(self) -> None:
        der = _generate_self_signed(sans=None)
        cert = _parse_x509("example.com", der)
        assert cert.subject_alt_names == []

    def test_fingerprint_is_stable_across_runs(self) -> None:
        der = _generate_self_signed(common_name="stable.example.com")
        cert1 = _parse_x509("stable.example.com", der)
        cert2 = _parse_x509("stable.example.com", der)
        assert cert1.fingerprint_sha256 == cert2.fingerprint_sha256


# ---------------------------------------------------------------------
# fetch_certificate — сетевые сценарии (всё замокано)
# ---------------------------------------------------------------------


@pytest.mark.asyncio
class TestFetchCertificate:
    async def test_invalid_domain_returns_invalid_certificate_error(self) -> None:
        result = await fetch_certificate("")
        assert isinstance(result, SSLError)
        assert result.error_type == "invalid_certificate"

    async def test_timeout_classified(self) -> None:
        with patch(
            "src.ssl.client.asyncio.open_connection",
            new=AsyncMock(side_effect=TimeoutError),
        ):
            result = await fetch_certificate("example.com")
        assert isinstance(result, SSLError)
        assert result.error_type == "connection_timeout"
        assert result.domain == "example.com"

    async def test_asyncio_wait_for_timeout_classified(self) -> None:
        # asyncio.wait_for бросает asyncio.TimeoutError (= TimeoutError).
        async def hanging(*_args, **_kwargs):  # type: ignore[no-untyped-def]
            await asyncio.sleep(100)

        with patch("src.ssl.client.asyncio.open_connection", side_effect=hanging), \
             patch("src.ssl.client.CONNECT_TIMEOUT", 0.01):
            result = await fetch_certificate("example.com")
        assert isinstance(result, SSLError)
        assert result.error_type == "connection_timeout"

    async def test_connection_refused_classified_as_no_https(self) -> None:
        # Port 443 closed = у домена нет HTTPS, это не алерт.
        with patch(
            "src.ssl.client.asyncio.open_connection",
            new=AsyncMock(side_effect=ConnectionRefusedError("port closed")),
        ):
            result = await fetch_certificate("example.com")
        assert isinstance(result, SSLError)
        assert result.error_type == "no_https"

    async def test_ssl_handshake_failure_classified(self) -> None:
        with patch(
            "src.ssl.client.asyncio.open_connection",
            new=AsyncMock(side_effect=ssl_module.SSLError("WRONG_VERSION_NUMBER")),
        ):
            result = await fetch_certificate("example.com")
        assert isinstance(result, SSLError)
        assert result.error_type == "tls_handshake_failed"

    async def test_dns_failure_classified_as_no_https(self) -> None:
        err = socket.gaierror(-2, "Name or service not known")
        with patch(
            "src.ssl.client.asyncio.open_connection",
            new=AsyncMock(side_effect=err),
        ):
            result = await fetch_certificate("nonexistent.invalid")
        assert isinstance(result, SSLError)
        assert result.error_type == "no_https"

    async def test_network_unreachable_classified_as_no_https(self) -> None:
        err = OSError(101, "Network is unreachable")
        with patch(
            "src.ssl.client.asyncio.open_connection",
            new=AsyncMock(side_effect=err),
        ):
            result = await fetch_certificate("example.com")
        assert isinstance(result, SSLError)
        assert result.error_type == "no_https"

    async def test_no_address_associated_classified_as_no_https(self) -> None:
        err = OSError(-5, "No address associated with hostname")
        with patch(
            "src.ssl.client.asyncio.open_connection",
            new=AsyncMock(side_effect=err),
        ):
            result = await fetch_certificate("example.com")
        assert isinstance(result, SSLError)
        assert result.error_type == "no_https"

    async def test_generic_oserror_classified_as_connection_refused(self) -> None:
        err = OSError(13, "Permission denied")
        with patch(
            "src.ssl.client.asyncio.open_connection",
            new=AsyncMock(side_effect=err),
        ):
            result = await fetch_certificate("example.com")
        assert isinstance(result, SSLError)
        assert result.error_type == "connection_refused"

    async def test_unexpected_exception_classified_as_internal_error(self) -> None:
        with patch(
            "src.ssl.client.asyncio.open_connection",
            new=AsyncMock(side_effect=RuntimeError("kaboom")),
        ):
            result = await fetch_certificate("example.com")
        assert isinstance(result, SSLError)
        assert result.error_type == "internal_error"

    async def test_successful_fetch_returns_certificate(self) -> None:
        der = _generate_self_signed(common_name="happy.example.com")

        # Reader/writer пара — writer.get_extra_info('ssl_object').getpeercert(True)
        # должно вернуть DER. close()/wait_closed() — no-op.
        ssl_obj = MagicMock()
        ssl_obj.getpeercert.return_value = der

        writer = MagicMock()
        writer.get_extra_info.return_value = ssl_obj
        writer.close = MagicMock()
        writer.wait_closed = AsyncMock()

        reader = MagicMock()

        async def fake_open_connection(*_args, **_kwargs):  # type: ignore[no-untyped-def]
            return reader, writer

        with patch("src.ssl.client.asyncio.open_connection", side_effect=fake_open_connection):
            result = await fetch_certificate("happy.example.com")

        assert isinstance(result, SSLCertificate)
        assert result.subject_cn == "happy.example.com"
        assert result.has_certificate is True
        writer.close.assert_called_once()

    async def test_missing_ssl_object_returns_error(self) -> None:
        writer = MagicMock()
        writer.get_extra_info.return_value = None
        writer.close = MagicMock()
        writer.wait_closed = AsyncMock()

        async def fake_open_connection(*_args, **_kwargs):  # type: ignore[no-untyped-def]
            return MagicMock(), writer

        with patch("src.ssl.client.asyncio.open_connection", side_effect=fake_open_connection):
            result = await fetch_certificate("example.com")

        assert isinstance(result, SSLError)
        assert result.error_type == "tls_handshake_failed"

    async def test_empty_peer_cert_returns_invalid_certificate(self) -> None:
        ssl_obj = MagicMock()
        ssl_obj.getpeercert.return_value = b""

        writer = MagicMock()
        writer.get_extra_info.return_value = ssl_obj
        writer.close = MagicMock()
        writer.wait_closed = AsyncMock()

        async def fake_open_connection(*_args, **_kwargs):  # type: ignore[no-untyped-def]
            return MagicMock(), writer

        with patch("src.ssl.client.asyncio.open_connection", side_effect=fake_open_connection):
            result = await fetch_certificate("example.com")

        assert isinstance(result, SSLError)
        assert result.error_type == "invalid_certificate"

    async def test_garbage_peer_cert_returns_invalid_certificate(self) -> None:
        ssl_obj = MagicMock()
        ssl_obj.getpeercert.return_value = b"not-a-valid-der"

        writer = MagicMock()
        writer.get_extra_info.return_value = ssl_obj
        writer.close = MagicMock()
        writer.wait_closed = AsyncMock()

        async def fake_open_connection(*_args, **_kwargs):  # type: ignore[no-untyped-def]
            return MagicMock(), writer

        with patch("src.ssl.client.asyncio.open_connection", side_effect=fake_open_connection):
            result = await fetch_certificate("example.com")

        assert isinstance(result, SSLError)
        assert result.error_type == "invalid_certificate"

    async def test_idn_domain_normalized_in_open_connection(self) -> None:
        captured: dict[str, object] = {}

        async def fake_open_connection(host, port, **kwargs):  # type: ignore[no-untyped-def]
            captured["host"] = host
            captured["port"] = port
            captured["server_hostname"] = kwargs.get("server_hostname")
            raise ConnectionRefusedError("stop here")

        with patch("src.ssl.client.asyncio.open_connection", side_effect=fake_open_connection):
            await fetch_certificate("пример.рф")

        # Хост должен быть в punycode, не Unicode.
        assert captured["host"] == "xn--e1afmkfd.xn--p1ai"
        assert captured["server_hostname"] == "xn--e1afmkfd.xn--p1ai"
        assert captured["port"] == 443
