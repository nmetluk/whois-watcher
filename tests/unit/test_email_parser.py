"""Тесты ``src.email_intel.parser``: парсеры DNS записей."""

from __future__ import annotations

from src.email_intel.parser import (
    DKIM_SELECTORS,
    parse_dkim_selectors,
    parse_dmarc,
    parse_mx_records,
    parse_spf,
)


# Mock dnspython MX answer
class MockMXAnswer:
    def __init__(self, exchange: str, preference: int):
        self._exchange = exchange
        self.preference = preference

    @property
    def exchange(self) -> MockName:  # type: ignore
        return MockName(self._exchange)


class MockName:
    """Mock для dnspython Name."""

    def __init__(self, value: str):
        self.value = value

    def to_unicode(self) -> str:
        return self.value


class TestParseMXRecords:
    def test_empty_list(self) -> None:
        """Пустой список — пустой результат."""
        assert parse_mx_records([]) == []

    def test_single_record(self) -> None:
        """Один MX-запись."""
        answers = [MockMXAnswer(exchange="mail.example.com.", preference=10)]
        result = parse_mx_records(answers)
        assert len(result) == 1
        assert result[0].host == "mail.example.com"
        assert result[0].priority == 10

    def test_multiple_records_sorted(self) -> None:
        """Несколько записей сортируются по priority."""
        answers = [
            MockMXAnswer(exchange="mail2.example.com.", preference=20),
            MockMXAnswer(exchange="mail1.example.com.", preference=10),
        ]
        result = parse_mx_records(answers)
        assert len(result) == 2
        assert result[0].priority == 10
        assert result[1].priority == 20

    def test_host_normalized(self) -> None:
        """Host приводится к lower и без trailing dot."""
        answers = [MockMXAnswer(exchange="Mail.Example.COM.", preference=10)]
        result = parse_mx_records(answers)
        assert result[0].host == "mail.example.com"


class TestParseSPF:
    def test_no_spf_returns_none(self) -> None:
        """Нет SPF-записи — None."""
        assert parse_spf([]) is None

    def test_non_txt_returns_none(self) -> None:
        """TXT без v=spf1 — None."""
        assert parse_spf(["v=dkim1..."]) is None

    def test_simple_fail_all(self) -> None:
        """-all → fail."""
        result = parse_spf(["v=spf1 ip4:192.0.2.0/24 -all"])
        assert result is not None
        assert result.mode == "fail"
        assert result.raw == "v=spf1 ip4:192.0.2.0/24 -all"
        assert result.is_multiple is False

    def test_softfail_all(self) -> None:
        """~all → softfail."""
        result = parse_spf(["v=spf1 ~all"])
        assert result is not None
        assert result.mode == "softfail"

    def test_neutral_all(self) -> None:
        """?all → neutral."""
        result = parse_spf(["v=spf1 ?all"])
        assert result is not None
        assert result.mode == "neutral"

    def test_pass_all(self) -> None:
        """+all → pass."""
        result = parse_spf(["v=spf1 +all"])
        assert result is not None
        assert result.mode == "pass"

    def test_no_all_mechanism(self) -> None:
        """Нет all-механизма → none."""
        result = parse_spf(["v=spf1 ip4:192.0.2.0/24"])
        assert result is not None
        assert result.mode == "none"

    def test_multiple_spf_records(self) -> None:
        """Несколько SPF — is_multiple=True."""
        txt_records = [
            "v=spf1 -all",
            "v=spf1 include:_spf.google.com ~all",
        ]
        result = parse_spf(txt_records)
        assert result is not None
        assert result.is_multiple is True


class TestParseDMARC:
    def test_none_returns_none(self) -> None:
        """None → None."""
        assert parse_dmarc(None) is None

    def test_empty_string_returns_none(self) -> None:
        """Пустая строка → None."""
        assert parse_dmarc("") is None

    def test_non_dmarc_returns_none(self) -> None:
        """TXT без v=DMARC1 → None."""
        assert parse_dmarc("v=spf1...") is None

    def test_simple_none_policy(self) -> None:
        """p=none → парсится."""
        result = parse_dmarc("v=DMARC1; p=none")
        assert result is not None
        assert result.policy == "none"
        assert result.subpolicy is None
        assert result.pct is None

    def test_quarantine_policy(self) -> None:
        """p=quarantine → парсится."""
        result = parse_dmarc("v=DMARC1; p=quarantine")
        assert result is not None
        assert result.policy == "quarantine"

    def test_reject_policy(self) -> None:
        """p=reject → парсится."""
        result = parse_dmarc("v=DMARC1; p=reject")
        assert result is not None
        assert result.policy == "reject"

    def test_with_sp(self) -> None:
        """sp= → парсится."""
        result = parse_dmarc("v=DMARC1; p=none; sp=reject")
        assert result is not None
        assert result.policy == "none"
        assert result.subpolicy == "reject"

    def test_with_pct(self) -> None:
        """pct= → парсится."""
        result = parse_dmarc("v=DMARC1; p=none; pct=50")
        assert result is not None
        assert result.policy == "none"
        assert result.pct == 50

    def test_full_record(self) -> None:
        """Полная запись."""
        result = parse_dmarc("v=DMARC1; p=quarantine; sp=reject; pct=100")
        assert result is not None
        assert result.policy == "quarantine"
        assert result.subpolicy == "reject"
        assert result.pct == 100

    def test_no_p_returns_none(self) -> None:
        """Нет p= — None."""
        result = parse_dmarc("v=DMARC1; rua=mailto:dmarc@example.com")
        assert result is None

    def test_invalid_pct_ignored(self) -> None:
        """pct > 100 игнорируется."""
        result = parse_dmarc("v=DMARC1; p=none; pct=150")
        assert result is not None
        assert result.pct is None


class TestParseDKIMSelectors:
    def test_empty_returns_empty(self) -> None:
        """Пустой словарь — пустой результат."""
        result = parse_dkim_selectors({})
        assert result.selectors == []

    def test_found_selectors(self) -> None:
        """Найденные селекторы."""
        result = parse_dkim_selectors(
            {
                "google": "v=DKIM1; p=...",
                "default": "v=DKIM1; p=...",
            }
        )
        assert set(result.selectors) == {"default", "google"}

    def test_missing_p_key_not_counted(self) -> None:
        """Селектор без p= не считается найденным."""
        result = parse_dkim_selectors(
            {
                "google": "v=DKIM1; k=rsa;",
            }
        )
        assert "google" not in result.selectors

    def test_sorted_result(self) -> None:
        """Результат сортируется."""
        result = parse_dkim_selectors(
            {
                "selector2": "v=DKIM1; p=...",
                "selector1": "v=DKIM1; p=...",
            }
        )
        assert result.selectors == ["selector1", "selector2"]


def test_dkim_selectors_constant() -> None:
    """Константа селекторов должна содержать ожидаемые значения."""
    assert ["default", "google", "selector1", "selector2", "k1", "mail"] == DKIM_SELECTORS
