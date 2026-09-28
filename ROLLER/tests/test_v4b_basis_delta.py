from __future__ import annotations

from roller.v4b.measurements import compute_observed
from tests.helpers_v4b import candle, fund, make_xt


def test_basis_delta_is_b_t_minus_b_prev():
    xt = make_xt(
        current=candle("2025-12-20T20:14:00Z", 8000),
        previous=candle("2025-12-20T20:13:00Z", 7000),
        f_t=fund(3, 4, "2025-12-20T20:15:00Z"),
        f_prev=fund(1, 2, "2025-12-20T20:13:00Z"),
    )
    obs = compute_observed(xt)
    assert obs["market_fundamental_basis"].value.fraction() == 500
    assert obs["basis_delta"].status == "valid"
    assert obs["basis_delta"].value.fraction() == 500 - 2000
