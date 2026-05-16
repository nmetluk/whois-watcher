"""Тесты ``src.whois.status_format`` (Этап 8)."""

from __future__ import annotations

from src.whois.status_format import (
    DEFAULT_EMOJI,
    FormattedStatus,
    format_statuses,
)


class TestFormatStatuses:
    def test_known_gtld_status_translated_ru(self) -> None:
        out = format_statuses(["clientTransferProhibited"], lang="ru")
        assert len(out) == 1
        item = out[0]
        assert item.raw_code == "clientTransferProhibited"
        assert item.text == "Защищён от трансфера"
        assert item.severity == "info"
        assert item.emoji == "🔒"
        assert item.is_known is True

    def test_known_status_translated_en(self) -> None:
        out = format_statuses(["clientHold"], lang="en")
        assert out[0].text == "On hold by registrar"
        assert out[0].severity == "critical"
        assert out[0].emoji == "🚨"

    def test_unknown_status_humanized(self) -> None:
        out = format_statuses(["someExoticStatus"], lang="ru")
        assert len(out) == 1
        item = out[0]
        assert item.is_known is False
        assert item.text == "Some exotic status"
        assert item.severity == "info"
        assert item.emoji == DEFAULT_EMOJI["info"]

    def test_unknown_upper_snake_humanized(self) -> None:
        out = format_statuses(["NOT_DELEGATED_HERE"], lang="ru")
        assert out[0].text == "Not delegated here"

    def test_sort_critical_first(self) -> None:
        out = format_statuses(
            ["ok", "clientTransferProhibited", "pendingDelete", "clientHold"],
            lang="ru",
        )
        sev_order = [item.severity for item in out]
        assert sev_order == ["critical", "critical", "info"]
        # ok должен быть скрыт (есть не-normal)
        assert all(item.raw_code != "ok" for item in out)

    def test_trivial_kept_when_alone(self) -> None:
        out = format_statuses(["ok"], lang="ru")
        assert len(out) == 1
        assert out[0].raw_code == "ok"

    def test_duplicates_collapsed(self) -> None:
        # Verisign дублирует Domain Status: в thick-WHOIS — нужно схлопывать.
        out = format_statuses(["clientTransferProhibited", "clientTransferProhibited"], lang="ru")
        assert len(out) == 1

    def test_disable_drop_trivial(self) -> None:
        out = format_statuses(
            ["ok", "pendingDelete"], lang="ru", drop_trivial_when_others_present=False
        )
        codes = {x.raw_code for x in out}
        assert codes == {"ok", "pendingDelete"}

    def test_empty_input(self) -> None:
        assert format_statuses([], lang="ru") == []

    def test_unknown_language_fallbacks_to_ru(self) -> None:
        out = format_statuses(["ok"], lang="xx")  # type: ignore[arg-type]
        assert out[0].text == "Активен"

    def test_returns_formatted_status_instances(self) -> None:
        out = format_statuses(["ok"], lang="ru")
        assert isinstance(out[0], FormattedStatus)
