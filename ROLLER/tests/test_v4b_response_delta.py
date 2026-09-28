from __future__ import annotations

from fractions import Fraction

from roller.v4b.measurements import compute_observed
from tests.helpers_v4b import candle, fund, make_xt


def test_response_delta_is_market_minus_fundamental():
    xt = make_xt(
        current=candle("2025-12-20T20:14:00Z", 7600),
        previous=candle("2025-12-20T20:13:00Z", 7400),
        f_t=fund(3, 4, "2025-12-20T20:15:00Z"),
        f_prev=fund(1, 2, "2025-12-20T20:13:00Z"),
    )
    obs = compute_observed(xt)
    # ΔK=200, ΔF=2500, response=-2300
    assert obs["response_delta"].value.fraction() == Fraction(-2300, 1)
    assert obs["response_delta"].status == "valid"


def test_response_delta_null_if_either_delta_null():
    xt = make_xt(f_t=fund(1, 4, "2025-12-20T20:15:00Z", status="INSUFFICIENT_SUPPORT"))
    obs = compute_observed(xt)
    assert obs["fundamental_delta"].value is None
    assert obs["response_delta"].value is None
    assert obs["response_delta"].status == "MISSING_F"
