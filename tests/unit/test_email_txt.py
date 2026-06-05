"""Тесты ``txt_to_str`` на РЕАЛЬНЫХ dnspython rdata (TASK-0089).

Урок инцидента TASK-0088: код звал несуществующий ``TXT.to_unicode()``,
а тесты мокали его (``MagicMock(to_unicode=...)``) и были зелёными.
Правило: TXT-извлечение тестируем только на настоящих rdata.
"""

from __future__ import annotations

import dns.rdata

from src.email_intel.txt import txt_to_str


def _rdata(text: str) -> dns.rdata.Rdata:
    return dns.rdata.from_text("IN", "TXT", text)


def test_simple_spf() -> None:
    r = _rdata('"v=spf1 include:_spf.example.com -all"')
    assert txt_to_str(r) == "v=spf1 include:_spf.example.com -all"


def test_real_rdata_has_no_to_unicode() -> None:
    """Сам инцидент: у настоящего TXT-rdata НЕТ to_unicode."""
    assert not hasattr(_rdata('"x"'), "to_unicode")


def test_multisegment_concatenated_without_separator() -> None:
    """Длинные TXT дробятся на 255-байтовые сегменты; склейка без разделителя (RFC 7208 §3.3)."""
    r = _rdata('"v=spf1 include:a.example.com " "include:b.example.com -all"')
    assert txt_to_str(r) == "v=spf1 include:a.example.com include:b.example.com -all"


def test_dmarc_record() -> None:
    r = _rdata('"v=DMARC1; p=quarantine; pct=100"')
    assert txt_to_str(r) == "v=DMARC1; p=quarantine; pct=100"


def test_non_ascii_bytes_do_not_raise() -> None:
    r = _rdata(r'"caf\195\169"')  # utf-8 байты é внутри TXT
    assert txt_to_str(r) == "café"


def test_fallback_object_with_to_text_only() -> None:
    class Weird:
        def to_text(self) -> str:
            return '"hello" "world"'

    assert txt_to_str(Weird()) == "helloworld"
