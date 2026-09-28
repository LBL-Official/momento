"""M_t — integer E4 candle observation. Candle path ≠ fill."""

from __future__ import annotations

from typing import Any

import pandas as pd

from roller.canonical.align import latest_candle
from roller.state.missingness import section


def market_state_section(
    candles: pd.DataFrame,
    *,
    as_of,
    end_of_day: bool = False,
) -> dict[str, Any]:
    if candles is None or candles.empty:
        return section("PARTIAL", None)
    latest = latest_candle(candles, as_of, end_of_day=end_of_day)
    if latest is None:
        return section("PARTIAL", None)
    rec = latest.to_dict()
    data = {
        "ticker": rec.get("ticker"),
        "team_side": rec.get("team_side"),
        "available_at": rec.get("available_at"),
        "yes_bid_close": rec.get("yes_bid_close"),
        "yes_ask_close": rec.get("yes_ask_close"),
        "yes_bid_open": rec.get("yes_bid_open"),
        "yes_ask_open": rec.get("yes_ask_open"),
        "volume": rec.get("volume"),
        "market_data_type": rec.get("market_data_type") or "CANDLESTICK_TOP_OF_BOOK",
        "note": "integer E4 top-of-book candle; not a fill",
    }
    return section("REAL", data)
