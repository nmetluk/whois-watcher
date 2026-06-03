"""Headless charts rendering for daily ops reports (ADR 042, TASK-0060).

Uses matplotlib Agg backend (must call matplotlib.use("Agg") before pyplot import).
All CPU-bound rendering must be wrapped in asyncio.to_thread by callers.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from io import BytesIO

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter

logger = __import__("logging").getLogger(__name__)


def _ensure_14_days(
    series: Sequence[tuple[date | datetime, int]], days: int = 14
) -> list[tuple[datetime, int]]:
    """Pad series to last `days` with zero counts for missing days. Dates normalized to date()."""
    if not series:
        today = datetime.now(UTC).date()
        return [
            (datetime.combine(today - timedelta(days=i), datetime.min.time(), tzinfo=UTC), 0)
            for i in range(days - 1, -1, -1)
        ]

    # Normalize to date, build map
    day_map: dict[date, int] = {}
    for ts, cnt in series:
        d = ts.date() if hasattr(ts, "date") else ts
        if isinstance(d, datetime):
            d = d.date()
        day_map[d] = day_map.get(d, 0) + cnt

    today = datetime.now(UTC).date()
    result: list[tuple[datetime, int]] = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        result.append((datetime.combine(d, datetime.min.time(), tzinfo=UTC), day_map.get(d, 0)))
    return result


async def render_daily_charts(
    series: dict[str, list[tuple[datetime, int]]],
    days: int = 14,
) -> bytes:
    """Render a 2x2 grid of daily line charts as PNG bytes.

    Expected keys: "lookups", "active", "new_domains", "notifications".
    Each value is list of (timestamp, count) for the period (will be padded).
    Returns raw PNG bytes. Never raises on empty data (shows placeholder).
    """

    def _render() -> bytes:
        padded = {k: _ensure_14_days(v or [], days) for k, v in series.items()}

        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        fig.suptitle(f"Daily metrics (last {days} days)", fontsize=14)

        configs = [
            ("lookups", "Lookups / day", axes[0, 0]),
            ("active", "Active users / day", axes[0, 1]),
            ("new_domains", "New domains / day", axes[1, 0]),
            ("notifications", "Notifications / day", axes[1, 1]),
        ]

        for key, title, ax in configs:
            data = padded.get(key, [])
            if not data:
                ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            else:
                xs = [d for d, _ in data]
                ys = [c for _, c in data]
                ax.plot(xs, ys, marker="o", linestyle="-", linewidth=1.5, markersize=4)
                ax.fill_between(xs, ys, alpha=0.2)
            ax.set_title(title)
            ax.grid(True, alpha=0.3)
            ax.xaxis.set_major_formatter(DateFormatter("%m-%d"))  # type: ignore[no-untyped-call]
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

        plt.tight_layout(rect=(0, 0.03, 1, 0.95))
        buf = BytesIO()
        plt.savefig(buf, format="png", dpi=120, bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)
        return buf.getvalue()

    try:
        return await asyncio.to_thread(_render)
    except Exception:
        logger.exception("charts: render failed, returning placeholder")
        # Fallback 1x1 placeholder PNG (minimal valid)
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "Chart render error", ha="center")
        buf = BytesIO()
        plt.savefig(buf, format="png")
        buf.seek(0)
        plt.close(fig)
        return buf.getvalue()


__all__ = ["render_daily_charts"]
