"""Тесты ``src.locales.t``."""

from __future__ import annotations

import logging

from src.locales import DEFAULT_LANG, LOCALES, t


class TestT:
    def test_returns_ru_by_default(self) -> None:
        assert t("errors.no_domain").startswith("❌")
        assert "/whois" in t("errors.no_domain")

    def test_returns_en_when_requested(self) -> None:
        result = t("errors.no_domain", "en")
        assert "Specify a domain" in result

    def test_format_substitution(self) -> None:
        result = t("commands.rmv.success", "ru", domain="example.com")
        assert "example.com" in result

    def test_format_substitution_en(self) -> None:
        result = t(
            "commands.add.success_no_data",
            "en",
            domain="example.com",
        )
        assert "example.com" in result

    def test_fallback_to_default_when_key_missing_in_lang(self) -> None:
        # Добавляем ключ только в RU, проверяем fallback из EN.
        LOCALES["ru"]["__test_fallback_key__"] = "только в ru"
        try:
            assert t("__test_fallback_key__", "en") == "только в ru"
        finally:
            LOCALES["ru"].pop("__test_fallback_key__", None)

    def test_unknown_lang_uses_default(self) -> None:
        result = t("errors.no_domain", "fr")  # такого языка нет
        assert result == LOCALES[DEFAULT_LANG]["errors.no_domain"]

    def test_missing_key_returns_key_and_warns(
        self, caplog: logging.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="src.locales"):
            result = t("nonexistent.key.path", "ru")
        assert result == "nonexistent.key.path"
        assert any("Missing locale key" in r.message for r in caplog.records)

    def test_all_ru_keys_present_in_en(self) -> None:
        """Гарантия консистентности: каждый RU-ключ имеет английский эквивалент.

        Тест-страховка от пропусков при добавлении новых строк.
        """
        ru_keys = set(LOCALES["ru"])
        en_keys = set(LOCALES["en"])
        missing = ru_keys - en_keys
        assert not missing, f"EN locale missing keys: {sorted(missing)}"
