"""Build info access with graceful fallback when generation script wasn't run.

``scripts/generate_build_info.sh`` создаёт ``src/_build_info.py`` ПЕРЕД
docker-сборкой. В рантайме мы импортируем его лениво и, если файл
отсутствует (например, при локальном запуске в dev без генерации),
возвращаем плейсхолдер. Это позволяет не падать в /version и в тестах.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BuildInfo:
    """Снимок git-состояния, на котором собирался образ."""

    app_version: str  # из pyproject.toml на момент сборки
    git_commit: str
    git_commit_short: str
    git_branch: str
    git_tag: str  # пустая строка, если HEAD не на тэге
    build_time: str  # ISO-8601 UTC или "unknown"


def get_build_info() -> BuildInfo:
    """Возвращает ``BuildInfo`` или плейсхолдер, если файл не сгенерирован.

    Импорт ``src._build_info`` отложенный — модуля может не быть.
    Любая иная ошибка (например, кривое содержимое) тоже даёт fallback,
    чтобы /version хотя бы что-то отдал.

    Поля читаются через ``getattr`` с дефолтами — на случай если кто-то
    держит в образе старую версию ``_build_info.py`` без новых полей
    (например, до Этапа 9.1, когда добавили ``APP_VERSION``).
    """
    try:
        bi: Any = importlib.import_module("src._build_info")
    except ImportError:
        return _placeholder()
    try:
        return BuildInfo(
            app_version=str(getattr(bi, "APP_VERSION", "") or "unknown"),
            git_commit=str(bi.GIT_COMMIT),
            git_commit_short=str(bi.GIT_COMMIT_SHORT),
            git_branch=str(bi.GIT_BRANCH),
            git_tag=str(bi.GIT_TAG),
            build_time=str(bi.BUILD_TIME),
        )
    except AttributeError:
        return _placeholder()


def _placeholder() -> BuildInfo:
    return BuildInfo(
        app_version="unknown",
        git_commit="unknown",
        git_commit_short="dev",
        git_branch="unknown",
        git_tag="",
        build_time="unknown",
    )


__all__ = ["BuildInfo", "get_build_info"]
