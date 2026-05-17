"""Тесты ``src.utils.version.get_app_version`` (Этап 9 / hotfix APP_VERSION)."""

from __future__ import annotations

import importlib
import sys
import types

import pytest

from src.utils.version import get_app_version


def _clear_build_info_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Удаляет уже импортированный ``src._build_info`` из ``sys.modules``,
    чтобы следующий ``from src._build_info import ...`` шёл по нашему пути.
    """
    monkeypatch.delitem(sys.modules, "src._build_info", raising=False)


class TestGetAppVersion:
    def test_returns_app_version_from_build_info(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _clear_build_info_cache(monkeypatch)
        fake = types.ModuleType("src._build_info")
        fake.APP_VERSION = "1.2.3"  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "src._build_info", fake)

        assert get_app_version() == "1.2.3"

    def test_falls_back_to_importlib_when_build_info_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Симулируем отсутствие _build_info: подсунем модуль, который
        # бросит ImportError при попытке достать APP_VERSION.
        _clear_build_info_cache(monkeypatch)

        # Подсунем модуль БЕЗ атрибута APP_VERSION → AttributeError при
        # ``from src._build_info import APP_VERSION``.
        fake = types.ModuleType("src._build_info")
        # APP_VERSION НЕ выставлен → from-import упадёт AttributeError → except.
        monkeypatch.setitem(sys.modules, "src._build_info", fake)

        # Подменяем importlib.metadata.version, чтобы вернуть фиксированную
        # строку независимо от состояния окружения.
        monkeypatch.setattr(
            importlib.metadata,
            "version",
            lambda name: "9.9.9-from-metadata" if name == "whois-watcher" else "wrong",
        )

        assert get_app_version() == "9.9.9-from-metadata"

    def test_returns_unknown_when_both_sources_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _clear_build_info_cache(monkeypatch)
        # _build_info есть, но без APP_VERSION.
        fake = types.ModuleType("src._build_info")
        monkeypatch.setitem(sys.modules, "src._build_info", fake)

        # importlib.metadata.version всегда бросает.
        def fake_version(name: str) -> str:
            raise importlib.metadata.PackageNotFoundError(name)

        monkeypatch.setattr(importlib.metadata, "version", fake_version)

        assert get_app_version() == "unknown"

    def test_empty_app_version_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Если в _build_info лежит пустая строка — это «не задано», не валим
        вывод пустотой, а пытаемся importlib-фолбэк."""
        _clear_build_info_cache(monkeypatch)
        fake = types.ModuleType("src._build_info")
        fake.APP_VERSION = ""  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "src._build_info", fake)
        monkeypatch.setattr(importlib.metadata, "version", lambda _n: "via-metadata")

        assert get_app_version() == "via-metadata"


class TestBuildInfoAppVersion:
    def test_buildinfo_includes_app_version(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.utils.build_info import get_build_info

        _clear_build_info_cache(monkeypatch)
        fake = types.ModuleType("src._build_info")
        fake.APP_VERSION = "0.2.0"  # type: ignore[attr-defined]
        fake.GIT_COMMIT = "abcdef1234567890"  # type: ignore[attr-defined]
        fake.GIT_COMMIT_SHORT = "abcdef1"  # type: ignore[attr-defined]
        fake.GIT_BRANCH = "main"  # type: ignore[attr-defined]
        fake.GIT_TAG = "v0.2.0"  # type: ignore[attr-defined]
        fake.BUILD_TIME = "2026-05-17T12:00:00Z"  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "src._build_info", fake)

        bi = get_build_info()
        assert bi.app_version == "0.2.0"
        assert bi.git_commit_short == "abcdef1"

    def test_buildinfo_app_version_fallback_for_old_files(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Старый _build_info.py без APP_VERSION → app_version='unknown',
        без AttributeError-падения."""
        from src.utils.build_info import get_build_info

        _clear_build_info_cache(monkeypatch)
        fake = types.ModuleType("src._build_info")
        # APP_VERSION НЕ установлен (старая версия скрипта)
        fake.GIT_COMMIT = "abcdef1234567890"  # type: ignore[attr-defined]
        fake.GIT_COMMIT_SHORT = "abcdef1"  # type: ignore[attr-defined]
        fake.GIT_BRANCH = "main"  # type: ignore[attr-defined]
        fake.GIT_TAG = ""  # type: ignore[attr-defined]
        fake.BUILD_TIME = "2026-05-17T12:00:00Z"  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "src._build_info", fake)

        bi = get_build_info()
        assert bi.app_version == "unknown"
        assert bi.git_commit_short == "abcdef1"
