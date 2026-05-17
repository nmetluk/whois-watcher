"""Версия установленного пакета.

Primary source — ``src._build_info.APP_VERSION``, который запекается в
образ скриптом ``scripts/generate_build_info.sh`` из ``pyproject.toml``.
Это нужно потому что Dockerfile собирается с ``uv sync --no-install-project``
и ``importlib.metadata`` не находит пакет ``whois-watcher`` в рантайме.

Fallback — ``importlib.metadata.version("whois-watcher")``: работает в
dev-окружении после ``uv sync`` без ``--no-install-project``.

Если ни то, ни другое не сработало — возвращаем ``"unknown"``, чтобы
``/version`` хотя бы не падал.
"""

from __future__ import annotations

import importlib.metadata


def get_app_version() -> str:
    """``whois-watcher`` package version или ``"unknown"``."""
    # Primary: build-time бейк из pyproject.toml.
    try:
        from src._build_info import APP_VERSION

        if APP_VERSION:
            return str(APP_VERSION)
    except (ImportError, AttributeError):
        pass

    # Fallback: importlib.metadata — работает, если проект установлен
    # как пакет (dev-окружение, локальный ``uv sync``).
    try:
        return importlib.metadata.version("whois-watcher")
    except (importlib.metadata.PackageNotFoundError, ImportError):
        return "unknown"


__all__ = ["get_app_version"]
