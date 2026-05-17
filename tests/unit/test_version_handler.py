"""Тесты ``/version`` (Этап 9).

Проверяем три ветки:

1. Без сгенерированного ``_build_info`` → fallback на "unknown"/"dev".
2. Обычный пользователь → короткий вывод, без admin-секций.
3. Админ → расширенный вывод (компоненты, storage, stack).
"""

from __future__ import annotations

import sys
import types
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.utils.build_info import BuildInfo, get_build_info

# ---------------------------------------------------------------------------
# build_info module
# ---------------------------------------------------------------------------


class TestBuildInfoFallback:
    def test_returns_placeholder_when_module_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Гарантируем что _build_info НЕ закэширован.
        monkeypatch.delitem(sys.modules, "src._build_info", raising=False)

        import src.utils.build_info as bi_module

        def fake_import_module(name: str):  # type: ignore[no-untyped-def]
            if name == "src._build_info":
                raise ImportError("simulated missing module")
            raise AssertionError(f"unexpected import of {name}")

        monkeypatch.setattr(bi_module.importlib, "import_module", fake_import_module)

        info = get_build_info()
        assert info.git_commit == "unknown"
        assert info.git_commit_short == "dev"
        assert info.git_tag == ""
        assert info.build_time == "unknown"

    def test_reads_from_generated_module(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Подсовываем фейковый _build_info-модуль в sys.modules.
        fake = types.ModuleType("src._build_info")
        fake.GIT_COMMIT = "abcdef1234567890"  # type: ignore[attr-defined]
        fake.GIT_COMMIT_SHORT = "abcdef1"  # type: ignore[attr-defined]
        fake.GIT_BRANCH = "main"  # type: ignore[attr-defined]
        fake.GIT_TAG = "v0.3.0"  # type: ignore[attr-defined]
        fake.BUILD_TIME = "2026-05-17T12:00:00Z"  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "src._build_info", fake)

        info = get_build_info()
        assert info.git_commit == "abcdef1234567890"
        assert info.git_commit_short == "abcdef1"
        assert info.git_branch == "main"
        assert info.git_tag == "v0.3.0"
        assert info.build_time == "2026-05-17T12:00:00Z"


# ---------------------------------------------------------------------------
# /version handler
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _noop_session():
    yield AsyncMock()


def _settings(*, admin_ids: list[int] | None = None, env: str = "test"):
    settings = MagicMock()
    settings.admin_user_ids = admin_ids or []
    settings.environment = env
    return settings


def _user(*, telegram_id: int = 12345):
    user = MagicMock()
    user.telegram_id = telegram_id
    return user


def _redis_stub(version: str | None = "7.4.9", ok: bool = True):
    redis = MagicMock()
    if ok:
        redis.info = AsyncMock(return_value={"redis_version": version} if version else {})
    else:
        redis.info = AsyncMock(side_effect=RuntimeError("redis down"))
    return redis


def _build_info_patch(monkeypatch: pytest.MonkeyPatch, info: BuildInfo) -> None:
    from src.bot.handlers import version as version_module

    monkeypatch.setattr(version_module, "get_build_info", lambda: info)
    monkeypatch.setattr(version_module, "get_app_version", lambda: "0.3.0")


class TestVersionHandler:
    async def test_short_output_for_regular_user(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.bot.handlers.version import cmd_version

        info = BuildInfo(
            app_version="0.3.0",
            git_commit="abcdef1234567890",
            git_commit_short="abcdef1",
            git_branch="main",
            git_tag="v0.3.0",
            build_time="2026-05-17T12:00:00Z",
        )
        _build_info_patch(monkeypatch, info)

        message = AsyncMock()
        message.answer = AsyncMock()

        await cmd_version(
            message=message,
            user=_user(telegram_id=999),
            lang="ru",
            settings=_settings(admin_ids=[111, 222]),  # 999 — не админ
            redis=_redis_stub(),
        )

        message.answer.assert_awaited_once()
        body = message.answer.await_args.args[0]
        assert "Whois Watcher" in body
        assert "Version: 0.3.0" in body
        assert "abcdef1" in body
        # короткий вывод НЕ содержит admin-секций
        assert "Components:" not in body
        assert "Storage:" not in body
        assert "GitHub:" not in body

    async def test_full_output_for_admin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.bot.handlers import version as version_module
        from src.bot.handlers.version import cmd_version

        info = BuildInfo(
            app_version="0.3.0",
            git_commit="abcdef1234567890",
            git_commit_short="abcdef1",
            git_branch="main",
            git_tag="v0.3.0",
            build_time="2026-05-17T12:00:00Z",
        )
        _build_info_patch(monkeypatch, info)

        # Stub'аем БД-вызовы и storage.
        monkeypatch.setattr(
            version_module, "_postgres_version", AsyncMock(return_value="PostgreSQL 16.4")
        )
        monkeypatch.setattr(
            version_module,
            "_storage_stats",
            AsyncMock(
                return_value={
                    "users": 42,
                    "user_domains": 137,
                    "whois_cache": 89,
                    "due_checks": 3,
                }
            ),
        )

        message = AsyncMock()
        message.answer = AsyncMock()

        admin_tg_id = 111
        await cmd_version(
            message=message,
            user=_user(telegram_id=admin_tg_id),
            lang="en",
            settings=_settings(admin_ids=[admin_tg_id], env="production"),
            redis=_redis_stub(version="7.4.9"),
        )

        body = message.answer.await_args.args[0]
        assert "Components:" in body
        assert "Storage:" in body
        assert "GitHub: https://github.com/nmetluk/whois-watcher/tree/abcdef1234567890" in body
        assert "Postgres: PostgreSQL 16.4" in body
        assert "Redis:    7.4.9" in body
        assert "User-domains: 137" in body
        assert "Tag:     v0.3.0" in body
        assert "Env:     production" in body

    async def test_unreachable_components_show_negative(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.bot.handlers import version as version_module
        from src.bot.handlers.version import cmd_version

        info = BuildInfo(
            app_version="0.3.0",
            git_commit="abcdef1234567890",
            git_commit_short="abcdef1",
            git_branch="main",
            git_tag="",
            build_time="2026-05-17T12:00:00Z",
        )
        _build_info_patch(monkeypatch, info)
        monkeypatch.setattr(version_module, "_postgres_version", AsyncMock(return_value=None))
        monkeypatch.setattr(
            version_module,
            "_storage_stats",
            AsyncMock(
                return_value={
                    "users": -1,
                    "user_domains": -1,
                    "whois_cache": -1,
                    "due_checks": -1,
                }
            ),
        )

        message = AsyncMock()
        admin_tg_id = 555
        await cmd_version(
            message=message,
            user=_user(telegram_id=admin_tg_id),
            lang="en",
            settings=_settings(admin_ids=[admin_tg_id]),
            redis=_redis_stub(ok=False),
        )
        body = message.answer.await_args.args[0]
        assert "❌" in body
        assert "Postgres: unreachable" in body
        assert "Redis:    unreachable" in body


class TestUptimeFormat:
    def test_seconds(self) -> None:
        from src.bot.handlers.version import _format_uptime

        assert _format_uptime(45.7) == "45s"

    def test_minutes(self) -> None:
        from src.bot.handlers.version import _format_uptime

        assert _format_uptime(125.0) == "2m 5s"

    def test_hours(self) -> None:
        from src.bot.handlers.version import _format_uptime

        assert _format_uptime(7300.0) == "2h 1m"

    def test_days(self) -> None:
        from src.bot.handlers.version import _format_uptime

        # 3 дня + 4 часа + 5 минут
        s = 3 * 86400 + 4 * 3600 + 5 * 60
        assert _format_uptime(float(s)) == "3d 4h 5m"
