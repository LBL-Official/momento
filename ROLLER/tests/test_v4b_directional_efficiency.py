from __future__ import annotations

from fractions import Fraction

from roller.v4b.measurements import compute_observed
from tests.helpers_v4b import candle, make_xt


def test_directional_efficiency_abs_close_open_over_range():
    xt = make_xt(current=candle("2025-12-20T20:14:00Z", 5180, open_=5000, high=5200, low=4900))
    e = compute_observed(xt)["directional_efficiency"]
    assert e.status == "valid"
    assert e.value.fraction() == Fraction(180, 300)
    assert e.path_information_status == "UNORDERED_SUMMARY"


def test_directional_efficiency_null_on_zero_range():
    xt = make_xt(current=candle("2025-12-20T20:14:00Z", 5000, open_=5000, high=5000, low=5000))
    e = compute_observed(xt)["directional_efficiency"]
    assert e.value is None
    assert e.status == "ZERO_RANGE"
