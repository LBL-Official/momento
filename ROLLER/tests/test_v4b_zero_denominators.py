from __future__ import annotations

from roller.v4b.measurements import compute_observed
from tests.helpers_v4b import candle, make_xt


def test_zero_score_elapsed_and_range_do_not_divide():
    xt = make_xt(
        s_t=5,
        s_prev=5,
        elapsed_t=100,
        elapsed_prev=100,
        current=candle("2025-12-20T20:14:00Z", 5000, open_=5000, high=5000, low=5000),
    )
    obs = compute_observed(xt)
    assert obs["score_delta"].status == "ZERO_SCORE_DELTA"
    assert obs["theta_observed"].status == "ZERO_ELAPSED"
    assert obs["directional_efficiency"].status == "ZERO_RANGE"
    assert obs["score_delta"].value is None
    assert obs["theta_observed"].value is None
    assert obs["directional_efficiency"].value is None
