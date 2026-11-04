"""One-line summaries for the ops channel."""
from __future__ import annotations

from .series import daily_changes, max_drawdown


def summarise(symbol: str, prices: list[float]) -> str:
    """Format the latest price, direction and drawdown for ``symbol``."""
    if not prices:
        return f"{symbol}: no data"
    latest = prices[-1]
    move = daily_changes(prices[-2:]) if len(prices) > 1 else []
    direction = "flat" if not move else ("up" if move[0] > 0 else "down")
    return (f"{symbol}: {latest:.2f} ({direction}, "
            f"drawdown {max_drawdown(prices):.2f}%)")
