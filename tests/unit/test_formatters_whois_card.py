"""Тесты ``src.services.formatters.format_whois_response`` (Этап 8).

Проверяем:

- секция «Владелец» появляется при наличии organization
- ``is_redacted`` без имени → «Скрыт (приватность)»
- ``Private Person`` → «Скрыт (физ.лицо)»
- contact отсутствует — секция не рендерится
- статусы переведены и отсортированы (critical первыми)
- тривиальный ``ok`` скрыт при наличии других
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.services.formatters import format_whois_response
from src.whois.types import WhoisContact, WhoisData


def _data(**kwargs: object) -> WhoisData:
    base: dict[str, object] = {
        "domain": "example.com",
        "is_registered": True,
        "expires_at": datetime(2027, 3, 15, tzinfo=UTC),
        "registrar": "Example Registrar Inc.",
    }
    base.update(kwargs)
    return WhoisData(**base)  # type: ignore[arg-type]


NOW = datetime(2026, 5, 16, 12, 0, tzinfo=UTC)


class TestOwnerSection:
    def test_organization_with_country(self) -> None:
        data = _data(
            contacts=[
                WhoisContact(
                    role="registrant",
                    organization="Example Holdings",
                    country="US",
                )
            ]
        )
        out = format_whois_response(data, lang="ru", now=NOW)
        assert "👤 Владелец: Example Holdings (US)" in out

    def test_organization_without_country(self) -> None:
        data = _data(contacts=[WhoisContact(role="registrant", organization="Example Holdings")])
        out = format_whois_response(data, lang="ru", now=NOW)
        assert "👤 Владелец: Example Holdings" in out
        assert "Example Holdings (" not in out

    def test_private_person_redacted(self) -> None:
        data = _data(
            contacts=[
                WhoisContact(
                    role="registrant",
                    name="Private Person",
                    is_redacted=True,
                )
            ]
        )
        out = format_whois_response(data, lang="ru", now=NOW)
        assert "👤 Владелец: Скрыт (физ.лицо)" in out

    def test_generic_privacy_redacted(self) -> None:
        data = _data(contacts=[WhoisContact(role="registrant", is_redacted=True)])
        out = format_whois_response(data, lang="ru", now=NOW)
        assert "👤 Владелец: Скрыт (приватность)" in out

    def test_section_hidden_when_no_contact(self) -> None:
        data = _data(contacts=[])
        out = format_whois_response(data, lang="ru", now=NOW)
        assert "👤" not in out
        assert "Владелец" not in out

    def test_section_hidden_when_empty_contact(self) -> None:
        """Контакт без полей (всё None, не redacted) — секция скрыта."""
        data = _data(contacts=[WhoisContact(role="registrant")])
        out = format_whois_response(data, lang="ru", now=NOW)
        assert "Владелец" not in out


class TestStatusSection:
    def test_translated_and_sorted_critical_first(self) -> None:
        data = _data(
            status=["ok", "clientTransferProhibited", "pendingDelete"],
        )
        out = format_whois_response(data, lang="ru", now=NOW)
        # Тривиальный "ok" скрыт; остаётся 2 статуса с критическим первым.
        assert "Активен" not in out
        assert "Скоро будет удалён" in out
        # critical должен идти раньше info в выводе
        idx_critical = out.index("Скоро будет удалён")
        idx_info = out.index("Защищён от трансфера")
        assert idx_critical < idx_info

    def test_ok_kept_when_alone(self) -> None:
        data = _data(status=["ok"])
        out = format_whois_response(data, lang="ru", now=NOW)
        assert "Активен" in out

    def test_unknown_status_humanized(self) -> None:
        data = _data(status=["exoticThing"])
        out = format_whois_response(data, lang="ru", now=NOW)
        assert "Exotic thing" in out


class TestRegressionExistingFields:
    def test_registrar_still_rendered(self) -> None:
        data = _data()
        out = format_whois_response(data, lang="ru", now=NOW)
        assert "Example Registrar Inc." in out

    def test_unregistered_template_unchanged(self) -> None:
        data = WhoisData(domain="free.example", is_registered=False)
        out = format_whois_response(data, lang="ru", now=NOW)
        assert "не зарегистрирован" in out
