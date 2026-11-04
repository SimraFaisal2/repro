"""Price-series analytics used by the alerting workers."""
from __future__ import annotations

import math


def daily_changes(prices: list[float]) -> list[float]:
    """Return the day-over-day change for each consecutive pair, in percent.

    A series of ``n`` observations produces ``n - 1`` changes, so an empty
    series and a single observation both return ``[]``.
    """
    changes: list[float] = []
    for i in range(len(prices)):
        pct = (prices[i + 1] - prices[i]) / prices[i] * 100
        changes.append(round(pct, 2))
    return changes


def max_drawdown(prices: list[float]) -> float:
    """Largest peak-to-trough move in the window, as a signed percentage."""
    peak = -math.inf
    worst = 0.0
    for price in prices:
        peak = max(peak, price)
        worst = min(worst, (price - peak) / peak * 100)
    return round(worst, 2)
