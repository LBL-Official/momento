"""Documented finite-difference acceleration. No smoothing."""

from __future__ import annotations

import pandas as pd

from roller.greeks.gamma import acceleration_from_backward
from roller.measurement.backward import backward_measurements


def test_acceleration_is_second_difference():
    candles = pd.DataFrame(
        [
            {"available_at": "2025-12-20T20:11:00Z", "yes_bid_close": "1000", "yes_bid_open": "1000", "yes_bid_high": "1000", "yes_bid_low": "1000", "team_side": "home"},
            {"available_at": "2025-12-20T20:12:00Z", "yes_bid_close": "1100", "yes_bid_open": "1000", "yes_bid_high": "1100", "yes_bid_low": "1000", "team_side": "home"},
            {"available_at": "2025-12-20T20:13:00Z", "yes_bid_close": "1300", "yes_bid_open": "1100", "yes_bid_high": "1300", "yes_bid_low": "1100", "team_side": "home"},
        ]
    )
    back = backward_measurements(candles, "2025-12-20T20:14:00Z")
    acc = acceleration_from_backward(back)
    assert acc["value"] == 100
    assert acc["smoothing_policy"] == "none"
    assert acc["finite_difference"]
