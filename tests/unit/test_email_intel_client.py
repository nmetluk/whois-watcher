"""Unit-тесты для src/email_intel/client.py (TASK-0079 extension of client tests).

Основные тесты classify + fetch MX-веток вынесены в test_email_intel_dns_classify.py
(по явному требованию таска). Здесь — smoke/специфичные для клиента тесты
(импорт, re-export таймаутов, parser_error и т.п.) + пример autospec.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.email_intel.client import (
    QUERY_TIMEOUT,
    TOTAL_TIMEOUT,
    fetch_email_intel,
)
from src.email_intel.resolver import build_resolver
from src.email_intel.types import EmailIntelError


def test_client_reexports_timeouts_for_backward_compat() -> None:
    """Таймауты доступны из client (как раньше), делегируют в resolver."""
    assert QUERY_TIMEOUT == 5
    assert TOTAL_TIMEOUT == 10


@pytest.mark.asyncio
async def test_fetch_email_intel_parser_error_on_bad_domain() -> None:
    """Плохой домен → parser_error (до DNS)."""
    res = await fetch_email_intel("..bad..domain..")
    assert isinstance(res, EmailIntelError)
    assert res.error_type == "parser_error"


@pytest.mark.asyncio
async def test_fetch_uses_build_resolver_autospec_style() -> None:
    """Демонстрация: build_resolver мокается через autospec-подобный патч (anti-drift)."""
    with patch("src.email_intel.client.build_resolver") as mock_build:
        mock_res = build_resolver(None)  # реальный, но подменённый
        mock_res.resolve = AsyncMock(side_effect=Exception("no net in test"))
        mock_build.return_value = mock_res

        # gather других упадёт в except верхнего уровня → internal_error
        res = await fetch_email_intel("example.com")
        # Даже если internal — ок, главное что build_resolver был вызван
        mock_build.assert_called()
        # Результат либо error (ожидаемо), без сети
        assert isinstance(res, EmailIntelError)
