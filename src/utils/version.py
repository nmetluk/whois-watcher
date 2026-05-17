"""Версия установленного пакета через ``importlib.metadata``.

В рантайме пакет ставится через ``uv sync`` / ``pip install`` — версия
читается из ``[project].version`` ``pyproject.toml``. В тестах / dev
без установки → ``"unknown"``.
"""

from __future__ import annotations

import importlib.metadata


def get_app_version() -> str:
    """``whois-watcher`` package version or ``"unknown"`` if not installed."""
    try:
        return importlib.metadata.version("whois-watcher")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


__all__ = ["get_app_version"]
