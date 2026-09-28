"""Market level, displacement, travel, range, MARKET_PRICE_VOLATILITY_V1."""

from __future__ import annotations

import statistics
from typing import Sequence

from roller.base_terminal_efficiency.versions import (
    MARKET_VOL_MIN_BARS,
    MARKET_VOL_RECENT_DIFFS,
    MARKET_VOL_RECENT_MIN_DIFFS,
)


def first_differences(closes: Sequence[int]) -> list[int]:
    return [closes[i] - closes[i - 1] for i in range(1, len(closes))]


def path_travel_e4(closes: Sequence[int]) -> int:
    return sum(abs(d) for d in first_differences(closes))


def market_path_metrics(closes: Sequence[int]) -> dict[str, int | float | None]:
    if not closes:
        return {
            "initial_market_price_e4": None,
            "signed_price_displacement_e4": None,
            "absolute_price_displacement_e4": None,
            "cumulative_price_travel_e4": None,
            "max_price_pre_entry_e4": None,
            "min_price_pre_entry_e4": None,
            "price_path_range_e4": None,
            "entry_price_volatility": None,
            "recent_entry_price_volatility": None,
        }
    k0 = int(closes[0])
    kt = int(closes[-1])
    disp = kt - k0
    diffs = first_differences(closes)
    vol = None
    if len(closes) >= MARKET_VOL_MIN_BARS:
        vol = float(statistics.stdev(diffs))
    recent = None
    tail = diffs[-MARKET_VOL_RECENT_DIFFS:]
    if len(tail) >= MARKET_VOL_RECENT_MIN_DIFFS:
        recent = float(statistics.stdev(tail))
    return {
        "initial_market_price_e4": k0,
        "signed_price_displacement_e4": disp,
        "absolute_price_displacement_e4": abs(disp),
        "cumulative_price_travel_e4": path_travel_e4(closes),
        "max_price_pre_entry_e4": max(closes),
        "min_price_pre_entry_e4": min(closes),
        "price_path_range_e4": max(closes) - min(closes),
        "entry_price_volatility": vol,
        "recent_entry_price_volatility": recent,
    }
