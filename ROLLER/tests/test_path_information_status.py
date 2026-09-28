"""OHLC-derived objects are unordered summaries, not ordered paths."""

from __future__ import annotations

import pandas as pd

from roller.measurement.backward import backward_measurements


def test_ohlc_path_is_unordered_summary():
    candles = pd.DataFrame(
        [
            {
                "available_at": "2025-12-20T20:13:30Z",
                "yes_bid_open": "5000",
                "yes_bid_high": "5100",
                "yes_bid_low": "4900",
                "yes_bid_close": "5050",
                "team_side": "home",
            }
        ]
    )
    out = backward_measurements(candles, "2025-12-20T20:14:00Z")
    meas = out["data"]["measurements"]
    for name in ("open_to_close_delta_1m", "high_low_range_1m", "directional_efficiency"):
        assert meas[name]["path_information_status"] == "UNORDERED_SUMMARY"
