from __future__ import annotations

from roller.v4b.measurements import compute_observed
from tests.helpers_v4b import candle, make_xt


def test_absolute_return_is_unsigned_abs_of_market_delta():
    xt = make_xt(
        current=candle("2025-12-20T20:14:00Z", 6900),
        previous=candle("2025-12-20T20:13:00Z", 7400),
    )
    obs = compute_observed(xt)
    assert obs["market_delta_1m"].value.numerator == -500
    assert obs["absolute_return"].value.numerator == 500
    assert obs["absolute_return"].value.numerator > 0
    assert obs["absolute_return"].status == "valid"


def test_absolute_return_null_iff_market_delta_null():
    xt = make_xt(
        current=candle("2025-12-20T20:14:00Z", 7500),
        previous=candle("2025-12-20T20:12:30Z", 7400),
    )
    obs = compute_observed(xt)
    assert obs["market_delta_1m"].value is None
    assert obs["absolute_return"].value is None
    assert obs["absolute_return"].status == obs["market_delta_1m"].status
