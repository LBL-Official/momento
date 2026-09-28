from __future__ import annotations

from fractions import Fraction

from roller.v4b.fundamentals import adapt_fundamental
from roller.v4b.measurements import compute_observed
from tests.helpers_v4b import candle, fund, make_xt


def test_f_e4_is_wins_times_10000_over_n_not_floor():
    view = adapt_fundamental(
        {
            "status": "IMPLEMENTED",
            "probability_wins": 2,
            "probability_n": 3,
            "value": {"numerator": 2, "denominator": 3},
            "available_at": "2025-12-20T20:15:00Z",
            "information_cutoff": "2025-12-20T20:15:00Z",
        }
    )
    assert view.ok
    assert 0 <= view.wins <= view.n
    assert view.f_e4() == Fraction(2 * 10000, 3)
    assert view.f_e4() != Fraction((2 * 10000) // 3, 1)
    assert view.basis(8000) == Fraction(8000 * 3 - 2 * 10000, 3)


def test_basis_public_value_stays_rational():
    xt = make_xt(
        current=candle("2025-12-20T20:14:00Z", 8000),
        f_t=fund(2, 3, "2025-12-20T20:15:00Z"),
    )
    b = compute_observed(xt)["market_fundamental_basis"]
    assert b.value.fraction() == Fraction(8000 * 3 - 2 * 10000, 3)
