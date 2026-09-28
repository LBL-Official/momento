from __future__ import annotations

import pandas as pd

from roller.v4b.candles import visible_home_candles
from roller.v4b.measurements import compute_observed
from tests.helpers_v4b import candle, make_xt


def test_non_60s_interval_is_time_gap():
    xt = make_xt(
        current=candle("2025-12-20T20:14:30Z", 7500),
        previous=candle("2025-12-20T20:13:00Z", 7400),
    )
    m = compute_observed(xt)["market_delta_1m"]
    assert m.value is None
    assert m.status == "TIME_GAP"
    assert m.provenance["interval_seconds"] == 90


def test_candle_at_exact_cutoff_is_hidden():
    rows = pd.DataFrame(
        [
            {"available_at": "2025-12-20T20:13:00Z", "yes_bid_close": 7400, "team_side": "home"},
            {"available_at": "2025-12-20T20:14:00Z", "yes_bid_close": 7500, "team_side": "home"},
            {"available_at": "2025-12-20T20:15:00Z", "yes_bid_close": 7600, "team_side": "home"},
        ]
    )
    vis = visible_home_candles(rows, "2025-12-20T20:15:00Z")
    assert [c.available_at for c in vis] == ["2025-12-20T20:13:00Z", "2025-12-20T20:14:00Z"]
    assert vis[-1].yes_bid_close == 7500
