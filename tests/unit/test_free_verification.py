"""Тесты RDAP-верификации «свободен» и строгой free-детекции (TASK-0092, ADR 045).

Инцидент TASK-0091: relay/TCI отдавал «No entries found» для уже
зарегистрированного discozavr.ru 2+ суток — бот уверенно показывал
«свободен». Правила:

- positive evidence (RDAP 200) бьёт negative («нет записи в WHOIS-тексте»);
- текст ошибки/рейтлимита/HTML — это сбой (WhoisError), а не «свободен»;
- неподтверждённый «свободен» помечается и рендерится осторожно.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.whois.client import _verify_unregistered
from src.whois.parser import looks_like_upstream_error
from src.whois.types import WhoisData, WhoisError

# Реальный ответ TCI из отчёта TASK-0091 (прод-улика)
TCI_NO_ENTRIES = (
    "% TCI Whois Service. Terms of use:\n"
    "% https://tcinet.ru/documents/whois_ru_rf.pdf (in Russian)\n\n"
    "No entries found for the selected source(s).\n\n"
    "Last updated on 2026-06-04T22:28:01Z\n"
)

# Минимальный RDAP-payload зарегистрированного домена (events → created)
RDAP_REGISTERED = {
    "objectClassName": "domain",
    "ldhName": "discozavr.ru",
    "status": ["active"],
    "events": [
        {"eventAction": "registration", "eventDate": "2026-06-03T10:00:00Z"},
        {"eventAction": "expiration", "eventDate": "2027-06-03T10:00:00Z"},
    ],
}


def _free(source: str = "proxy_whois_ru") -> WhoisData:
    return WhoisData(domain="discozavr.ru", is_registered=False, source=source)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_rdap_contradicts_whois_free_returns_registered() -> None:
    """Сам инцидент: WHOIS «нет записи», RDAP — registered → показываем ЗАНЯТ."""
    with patch("src.whois.client.query_rdap", AsyncMock(return_value=("found", RDAP_REGISTERED))):
        out = await _verify_unregistered(_free(), limits=None)
    assert isinstance(out, WhoisData)
    assert out.is_registered is True
    assert out.raw_data["free_contradicted_whois_source"] == "proxy_whois_ru"


@pytest.mark.asyncio
async def test_rdap_not_found_confirms_free() -> None:
    with patch("src.whois.client.query_rdap", AsyncMock(return_value=("not_found", None))):
        out = await _verify_unregistered(_free(), limits=None)
    assert isinstance(out, WhoisData)
    assert out.is_registered is False
    assert out.raw_data["free_verified"] == "rdap"
    assert "free_unverified" not in out.raw_data


@pytest.mark.parametrize("status", ["error", "unsupported"])
@pytest.mark.asyncio
async def test_rdap_unavailable_marks_unverified(status: str) -> None:
    with patch("src.whois.client.query_rdap", AsyncMock(return_value=(status, None))):
        out = await _verify_unregistered(_free(), limits=None)
    assert isinstance(out, WhoisData)
    assert out.is_registered is False
    assert out.raw_data["free_unverified"] is True


@pytest.mark.asyncio
async def test_registered_result_skips_verification() -> None:
    """Занятые домены не трогаем — и RDAP не дёргаем."""
    data = WhoisData(domain="example.com", is_registered=True, source="proxy_whois")
    with patch("src.whois.client.query_rdap", AsyncMock()) as q:
        out = await _verify_unregistered(data, limits=None)
    assert out is data
    q.assert_not_awaited()


@pytest.mark.asyncio
async def test_rdap_sourced_free_skips_verification() -> None:
    """«Свободен» от RDAP-источника — авторитетный 404, повторно не проверяем."""
    data = WhoisData(domain="example.com", is_registered=False, source="rdap")
    with patch("src.whois.client.query_rdap", AsyncMock()) as q:
        out = await _verify_unregistered(data, limits=None)
    assert out is data
    q.assert_not_awaited()


@pytest.mark.asyncio
async def test_whois_error_passes_through() -> None:
    err = WhoisError(domain="example.com", error_type="timeout", message="t/o")
    with patch("src.whois.client.query_rdap", AsyncMock()) as q:
        out = await _verify_unregistered(err, limits=None)
    assert out is err
    q.assert_not_awaited()


# ── строгая free-детекция: ошибки upstream ≠ «свободен» ─────────────


def test_tci_no_entries_is_not_upstream_error() -> None:
    """Легитимный «No entries» TCI — НЕ ошибка (free-путь, дальше RDAP-чек)."""
    assert looks_like_upstream_error(TCI_NO_ENTRIES) is False


@pytest.mark.parametrize(
    "text",
    [
        "You have exceeded allowed connection rate. Please slow down",
        "Error: rate limit reached, try again later",
        "<html><body><h1>502 Bad Gateway</h1></body></html>",
        "<!DOCTYPE html><title>Maintenance</title>",
        "Service unavailable, quota exceeded",
    ],
)
def test_error_like_texts_detected(text: str) -> None:
    assert looks_like_upstream_error(text) is True


def test_registered_whois_text_is_not_error() -> None:
    real = (
        "domain:         DISCOZAVR.RU\n"
        "nserver:        ns1.example.com.\n"
        "state:          REGISTERED, DELEGATED, VERIFIED\n"
        "registrar:      REGRU-RU\n"
        "created:        2026-06-03T10:00:00Z\n"
        "paid-till:      2027-06-03T10:00:00Z\n"
        "source:         TCI\n"
    )
    assert looks_like_upstream_error(real) is False


# ── рендер свободного домена через реальный t() (урок TASK-0046) ────


def test_format_free_verified_renders_confident() -> None:
    from src.services.formatters import format_whois_response

    data = WhoisData(domain="example.com", is_registered=False, source="proxy_whois")
    data.raw_data["free_verified"] = "rdap"
    out = format_whois_response(data, lang="ru")
    assert "свободен для регистрации" in out


def test_format_free_unverified_renders_cautious() -> None:
    from src.services.formatters import format_whois_response

    data = WhoisData(domain="example.com", is_registered=False, source="proxy_whois_ru")
    data.raw_data["free_unverified"] = True
    out = format_whois_response(data, lang="ru")
    assert "подтвердить" in out
    assert "свободен для регистрации" not in out
    assert "{domain}" not in out
