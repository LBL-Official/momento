"""Zero-range and insufficient-history volatility statuses."""

from __future__ import annotations

import pandas as pd

from roller.measurement.backward import backward_measurements


def test_zero_range_is_undefined_not_divided():
    candles = pd.DataFrame(
        [
            {
                "available_at": "2025-12-20T20:13:30Z",
                "yes_bid_open": "5000",
                "yes_bid_high": "5000",
                "yes_bid_low": "5000",
                "yes_bid_close": "5000",
                "team_side": "home",
            }
        ]
    )
    meas = backward_measurements(candles, "2025-12-20T20:14:00Z")["data"]["measurements"]
    assert meas["directional_efficiency"]["status"] == "undefined_zero_range"
    assert meas["directional_efficiency"]["value"] is None
    assert meas["close_to_close_realized_volatility"]["status"] == "insufficient_history"


def test_realized_vol_uses_visible_closes_only():
    candles = pd.DataFrame(
        [
            {
                "available_at": "2025-12-20T20:13:30Z",
                "yes_bid_open": "5000",
                "yes_bid_high": "5100",
                "yes_bid_low": "4900",
                "yes_bid_close": "5050",
                "team_side": "home",
            },
            {
                "available_at": "2025-12-20T20:15:00Z",
                "yes_bid_open": "5050",
                "yes_bid_high": "5200",
                "yes_bid_low": "5000",
                "yes_bid_close": "5180",
                "team_side": "home",
            },
        ]
    )
    early = backward_measurements(candles, "2025-12-20T20:14:00Z")["data"]["measurements"]
    assert early["close_to_close_realized_volatility"]["status"] == "insufficient_history"
    late = backward_measurements(candles, "2025-12-20T20:16:00Z")["data"]["measurements"]
    assert late["close_to_close_realized_volatility"]["value"] == 130
