from __future__ import annotations

from fractions import Fraction

from roller.v4b.measurements import compute_observed
from tests.helpers_v4b import candle, fund, make_xt


def test_basis_exact_rational_not_floor():
    xt = make_xt(
        current=candle("2025-12-20T20:14:00Z", 8000),
        f_t=fund(2, 3, "2025-12-20T20:15:00Z"),
    )
    b = compute_observed(xt)["market_fundamental_basis"]
    assert b.status == "valid"
    assert b.value.fraction() == Fraction(8000 * 3 - 2 * 10000, 3)
    assert (8000 * 3 - 2 * 10000) // 3 != b.value.fraction()


def test_basis_null_without_f():
    xt = make_xt(f_t=fund(1, 4, "2025-12-20T20:15:00Z", status="INSUFFICIENT_SUPPORT"))
    b = compute_observed(xt)["market_fundamental_basis"]
    assert b.value is None
    assert b.status == "MISSING_F"
