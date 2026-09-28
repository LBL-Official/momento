from __future__ import annotations

from roller.v4b.measurements import compute_observed
from tests.helpers_v4b import make_xt


def test_realized_market_volatility_is_abs_variation_sum():
    closes = [
        ("2025-12-20T20:10:00Z", 5000),
        ("2025-12-20T20:11:00Z", 5100),
        ("2025-12-20T20:12:00Z", 4900),
        ("2025-12-20T20:13:00Z", 4950),
    ]
    xt = make_xt(closes=closes, vol_window=10)
    v = compute_observed(xt)["realized_market_volatility"]
    assert v.status == "valid"
    assert v.value.numerator == 100 + 200 + 50
    assert v.provenance["not"] == ["implied_volatility", "standard_deviation", "sqrt_sum_squared_returns"]
    assert "stdev" not in str(v.public()).lower()


def test_realized_vol_uses_only_configured_window():
    closes = [(f"2025-12-20T20:{i:02d}:00Z", 1000 + i * 10) for i in range(8, 16)]
    xt = make_xt(closes=closes, vol_window=3)
    v = compute_observed(xt)["realized_market_volatility"]
    # last 3 closes: 1070, 1080, 1090 → |10|+|10|=20
    assert v.value.numerator == 20
    assert v.extra["n_changes"] == 2
