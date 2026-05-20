"""Тесты ASN-обогащения (Этап 14, ADR 032).

В v0.8.0 — placeholder, возвращает ``[]``. Тесты подтверждают
правильное поведение пустого вывода.
"""

from __future__ import annotations

from src.dns_monitor import enrich_with_asn


async def test_empty_input_returns_empty_list() -> None:
    assert await enrich_with_asn([]) == []


async def test_v080_placeholder_returns_empty_for_any_input() -> None:
    """В v0.8.0 функция всегда возвращает ``[]`` (placeholder).

    Когда rir2localdb получит endpoint IP→ASN — этот тест провалится
    и его нужно будет переписать на реальный lookup.
    """
    result = await enrich_with_asn(["1.2.3.4", "5.6.7.8"])
    assert result == []
