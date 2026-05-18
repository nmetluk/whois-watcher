"""Тесты ARQ-задачи ``rir_health_check`` (Этап 13 / ADR 031)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.rir_client import RIRStatus, RIRUnreachable, SyncRun
from src.tasks.rir_health import (
    MAX_SYNC_AGE,
    rir_health_check,
)


def _patch_settings(monkeypatch: pytest.MonkeyPatch, **overrides: Any) -> None:
    """Подменяет ``get_settings`` для модулей rir_health и AlertService."""
    base = {
        "rir2localdb_enabled": True,
        "admin_channel_id": -1001234567890,
    }
    base.update(overrides)
    stub = MagicMock()
    for k, v in base.items():
        setattr(stub, k, v)
    monkeypatch.setattr("src.tasks.rir_health.get_settings", lambda: stub)


def _patch_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Подменяет get_limits в rir_health.py — AlertService требует Limits."""
    stub = MagicMock()
    stub.alert_dedup_ttl_minutes = 60
    monkeypatch.setattr("src.tasks.rir_health.get_limits", lambda: stub)


def _make_ctx() -> dict[str, Any]:
    """ctx с моками bot+redis (как в реальном AlertService)."""
    bot = MagicMock()
    bot.send_message = AsyncMock()
    redis = MagicMock()
    # AlertService._reserve_dedup_slot вызывает self._redis.set(...) → True
    redis.set = AsyncMock(return_value=True)
    return {"bot": bot, "sync_redis": redis}


def _fresh_sync(status: str = "success") -> SyncRun:
    return SyncRun(
        id=1,
        tier="core",
        started_at=datetime.now(UTC) - timedelta(hours=2),
        finished_at=datetime.now(UTC) - timedelta(hours=2),
        status=status,
        stats={"duration_ms": 5000},
        error=None,
    )


def _stale_sync() -> SyncRun:
    return SyncRun(
        id=1,
        tier="core",
        started_at=datetime.now(UTC) - (MAX_SYNC_AGE + timedelta(hours=2)),
        finished_at=None,
        status="success",
        stats={},
        error=None,
    )


def _status_with(sync: SyncRun | None) -> RIRStatus:
    return RIRStatus(latest_sync_run=sync, sources=[], db_alive=True)


@pytest.mark.asyncio
class TestRirHealthCheck:
    async def test_disabled_skips_silently(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch, rir2localdb_enabled=False)
        _patch_limits(monkeypatch)
        # healthcheck не должен даже вызываться
        healthcheck_mock = AsyncMock(return_value=True)
        monkeypatch.setattr("src.tasks.rir_health.healthcheck", healthcheck_mock)
        ctx = _make_ctx()
        await rir_health_check(ctx)
        healthcheck_mock.assert_not_called()
        ctx["bot"].send_message.assert_not_called()

    async def test_missing_ctx_logs_and_returns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        _patch_limits(monkeypatch)
        healthcheck_mock = AsyncMock(return_value=True)
        monkeypatch.setattr("src.tasks.rir_health.healthcheck", healthcheck_mock)
        await rir_health_check({})  # нет bot/redis
        healthcheck_mock.assert_not_called()

    async def test_happy_path_no_alert(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        _patch_limits(monkeypatch)
        monkeypatch.setattr("src.tasks.rir_health.healthcheck", AsyncMock(return_value=True))
        monkeypatch.setattr(
            "src.tasks.rir_health.get_status",
            AsyncMock(return_value=_status_with(_fresh_sync())),
        )
        ctx = _make_ctx()
        await rir_health_check(ctx)
        ctx["bot"].send_message.assert_not_called()

    async def test_healthcheck_raises_sends_unreachable_alert(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_settings(monkeypatch)
        _patch_limits(monkeypatch)
        monkeypatch.setattr(
            "src.tasks.rir_health.healthcheck",
            AsyncMock(side_effect=RIRUnreachable("connection refused")),
        )
        ctx = _make_ctx()
        await rir_health_check(ctx)
        ctx["bot"].send_message.assert_awaited_once()
        text = ctx["bot"].send_message.await_args.kwargs["text"]
        assert "rir2localdb unreachable" in text
        assert "#critical" in text

    async def test_healthcheck_returns_false_sends_unhealthy_alert(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_settings(monkeypatch)
        _patch_limits(monkeypatch)
        monkeypatch.setattr("src.tasks.rir_health.healthcheck", AsyncMock(return_value=False))
        # get_status не должен вызываться
        get_status_mock = AsyncMock()
        monkeypatch.setattr("src.tasks.rir_health.get_status", get_status_mock)
        ctx = _make_ctx()
        await rir_health_check(ctx)
        get_status_mock.assert_not_called()
        ctx["bot"].send_message.assert_awaited_once()
        text = ctx["bot"].send_message.await_args.kwargs["text"]
        assert "rir2localdb unhealthy" in text

    async def test_get_status_unreachable_silently_returns(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_settings(monkeypatch)
        _patch_limits(monkeypatch)
        monkeypatch.setattr("src.tasks.rir_health.healthcheck", AsyncMock(return_value=True))
        monkeypatch.setattr(
            "src.tasks.rir_health.get_status",
            AsyncMock(side_effect=RIRUnreachable("status timeout")),
        )
        ctx = _make_ctx()
        await rir_health_check(ctx)
        ctx["bot"].send_message.assert_not_called()

    async def test_no_sync_runs_sends_no_sync_alert(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        _patch_limits(monkeypatch)
        monkeypatch.setattr("src.tasks.rir_health.healthcheck", AsyncMock(return_value=True))
        monkeypatch.setattr(
            "src.tasks.rir_health.get_status",
            AsyncMock(return_value=_status_with(None)),
        )
        ctx = _make_ctx()
        await rir_health_check(ctx)
        ctx["bot"].send_message.assert_awaited_once()
        text = ctx["bot"].send_message.await_args.kwargs["text"]
        assert "no sync runs yet" in text

    async def test_stale_sync_sends_stale_alert(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_settings(monkeypatch)
        _patch_limits(monkeypatch)
        monkeypatch.setattr("src.tasks.rir_health.healthcheck", AsyncMock(return_value=True))
        monkeypatch.setattr(
            "src.tasks.rir_health.get_status",
            AsyncMock(return_value=_status_with(_stale_sync())),
        )
        ctx = _make_ctx()
        await rir_health_check(ctx)
        ctx["bot"].send_message.assert_awaited_once()
        text = ctx["bot"].send_message.await_args.kwargs["text"]
        assert "stale" in text.lower()

    async def test_sync_failed_sends_sync_failed_alert(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_settings(monkeypatch)
        _patch_limits(monkeypatch)
        monkeypatch.setattr("src.tasks.rir_health.healthcheck", AsyncMock(return_value=True))
        monkeypatch.setattr(
            "src.tasks.rir_health.get_status",
            AsyncMock(return_value=_status_with(_fresh_sync(status="failure"))),
        )
        ctx = _make_ctx()
        await rir_health_check(ctx)
        ctx["bot"].send_message.assert_awaited_once()
        text = ctx["bot"].send_message.await_args.kwargs["text"]
        assert "sync_run failed" in text

    async def test_distinct_failure_modes_use_distinct_titles(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Дедуп AlertService по title — разные failure modes не должны
        перетирать друг друга в одном TTL-окне."""
        from src.tasks.rir_health import (
            _TITLE_NO_SYNC,
            _TITLE_STALE,
            _TITLE_SYNC_FAILED,
            _TITLE_UNHEALTHY,
            _TITLE_UNREACHABLE,
        )

        titles = {
            _TITLE_UNREACHABLE,
            _TITLE_UNHEALTHY,
            _TITLE_NO_SYNC,
            _TITLE_STALE,
            _TITLE_SYNC_FAILED,
        }
        # 5 уникальных строк → 5 уникальных hash-ключей дедупликации
        assert len(titles) == 5
