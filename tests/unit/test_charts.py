"""Unit tests for charts rendering (TASK-0060)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.services.charts import render_daily_charts


def _make_series(days: int = 5) -> dict[str, list[tuple[datetime, int]]]:
    base = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "lookups": [(base - timedelta(days=i), 10 + i) for i in range(days)],
        "active": [(base - timedelta(days=i), 5 + i) for i in range(days)],
        "new_domains": [(base - timedelta(days=i), 2) for i in range(days)],
        "notifications": [(base - timedelta(days=i), 20 - i) for i in range(days)],
    }


@pytest.mark.asyncio
async def test_render_daily_charts_produces_png() -> None:
    series = _make_series()
    png = await render_daily_charts(series)
    assert isinstance(png, bytes | bytearray)
    assert len(png) > 1000  # non-trivial PNG
    assert png[:4] == b"\x89PNG"  # PNG magic


@pytest.mark.asyncio
async def test_render_daily_charts_empty_data_placeholder() -> None:
    series: dict[str, list[tuple[datetime, int]]] = {
        "lookups": [],
        "active": [],
        "new_domains": [],
        "notifications": [],
    }
    png = await render_daily_charts(series)
    assert len(png) > 100  # still produces a PNG (with "No data" text)
    assert png[:4] == b"\x89PNG"


@pytest.mark.asyncio
async def test_render_daily_charts_partial_data() -> None:
    series = {
        "lookups": _make_series(3)["lookups"],
        "active": [],
        "new_domains": _make_series(3)["new_domains"],
        "notifications": [],
    }
    png = await render_daily_charts(series, days=3)
    assert len(png) > 500
