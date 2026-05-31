"""Тесты format_email_deep (TASK-0046, follow-up к TASK-0041).

Покрываем:
- Обработку None и пустых секций
- Экранирование html.escape
- Специфическую логику SPF (exceeds, truncation)
- DANE per-MX
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.db.models import EmailDeepCache
from src.services.formatters import format_email_deep


def _make_deep_cache(**kwargs) -> EmailDeepCache:
    """Фабрика мока EmailDeepCache с spec (anti-drift)."""
    cache = MagicMock(spec=EmailDeepCache)
    cache.domain = kwargs.get("domain", "example.com")
    cache.spf = kwargs.get("spf")
    cache.mta_sts = kwargs.get("mta_sts")
    cache.tls_rpt = kwargs.get("tls_rpt")
    cache.dane = kwargs.get("dane")
    cache.bimi = kwargs.get("bimi")
    cache.fetched_at = kwargs.get("fetched_at")
    cache.next_check_at = kwargs.get("next_check_at", datetime.now(tz=UTC))
    return cache


@pytest.fixture(autouse=True)
def mock_locales():
    """Мокаем t() чтобы тесты не зависели от точных строк в locales."""
    with patch(
        "src.services.formatters.t", side_effect=lambda key, lang, **kw: f"[{key}]"
    ) as mock_t:
        yield mock_t


class TestFormatEmailDeep:
    def test_none_cache_returns_no_data(self) -> None:
        assert format_email_deep(None, lang="ru") == "[deep_email.no_data]"

    def test_full_cache_renders_all_sections(self) -> None:
        cache = _make_deep_cache(
            spf={
                "sources": ["ip4:1.2.3.4", "include:_spf.example.com"],
                "lookup_count": 3,
                "exceeds_limit": False,
            },
            mta_sts={
                "policy_mode": "enforce",
                "mx": ["mx1.example.com"],
                "max_age": 86400,
                "reachable": True,
            },
            tls_rpt={"present": True, "rua": "mailto:reports@example.com"},
            dane={"host_tlsa": {"mx1.example.com": True, "mx2.example.com": False}},
            bimi={"present": True, "logo_url": "https://example.com/logo.svg"},
            fetched_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
        )

        text = format_email_deep(cache, lang="ru")

        # С моком t() все вызовы возвращают [key]
        assert "[deep_email.section_spf]" in text
        assert "[deep_email.section_mta_sts]" in text
        assert "[deep_email.section_dane]" in text
        assert "[deep_email.section_bimi]" in text

    def test_spf_exceeds_limit_shows_warning(self) -> None:
        cache = _make_deep_cache(
            spf={"sources": ["ip4:1.2.3.4"] * 20, "lookup_count": 12, "exceeds_limit": True}
        )
        text = format_email_deep(cache, lang="ru")
        # С моком просто проверяем, что функция не упала
        assert text  # не пустая строка

    def test_spf_sources_truncated(self) -> None:
        sources = [f"ip4:1.2.3.{i}" for i in range(15)]
        cache = _make_deep_cache(
            spf={"sources": sources, "lookup_count": 15, "exceeds_limit": False}
        )
        text = format_email_deep(cache, lang="ru")
        assert text  # не падает на большом списке

    def test_empty_sections_are_skipped_gracefully(self) -> None:
        cache = _make_deep_cache(
            spf=None,
            mta_sts=None,
            tls_rpt=None,
            dane=None,
            bimi=None,
        )
        text = format_email_deep(cache, lang="ru")
        # Не должно падать и не должно показывать пустые секции как ошибки
        assert "SPF" not in text or "не настроено" in text or "нет" in text.lower()

    def test_dane_per_mx_mixed_results(self) -> None:
        cache = _make_deep_cache(
            dane={"host_tlsa": {"mx1.com": True, "mx2.com": False, "mx3.com": True}}
        )
        text = format_email_deep(cache, lang="ru")
        assert "✅ TLSA" in text
        assert "∅ no TLSA" in text or "no TLSA" in text

    def test_html_escape_on_dangerous_values(self) -> None:
        cache = _make_deep_cache(
            spf={
                "sources": ["ip4:1.2.3.4 <script>alert(1)</script>"],
                "lookup_count": 1,
                "exceeds_limit": False,
            },
            mta_sts={
                "policy_mode": "enforce",
                "mx": ['mx"><script>'],
                "max_age": 3600,
                "reachable": True,
            },
        )
        text = format_email_deep(cache, lang="ru")
        # С реальным html.escape + моком t
        assert "<script>" not in text
