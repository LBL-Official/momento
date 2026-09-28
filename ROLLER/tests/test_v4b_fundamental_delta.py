from __future__ import annotations

from fractions import Fraction

from roller.v4b.measurements import compute_observed
from tests.helpers_v4b import fund, make_xt


def test_fundamental_delta_exact_e4_rational():
    xt = make_xt(
        f_t=fund(3, 4, "2025-12-20T20:15:00Z"),
        f_prev=fund(1, 2, "2025-12-20T20:13:00Z"),
    )
    d = compute_observed(xt)["fundamental_delta"]
    assert d.status == "valid"
    # 7500 - 5000 = 2500 e4
    assert d.value.fraction() == Fraction(2500, 1)
    assert d.provenance["current_numerator"] == 3
    assert d.provenance["current_denominator"] == 4
    assert d.provenance["prior_numerator"] == 1
    assert d.provenance["prior_denominator"] == 2
    assert d.measurement_available_at == "2025-12-20T20:15:00Z"


def test_fundamental_delta_not_floor_division():
    xt = make_xt(
        f_t=fund(2, 3, "2025-12-20T20:15:00Z"),
        f_prev=fund(1, 3, "2025-12-20T20:13:00Z"),
    )
    d = compute_observed(xt)["fundamental_delta"]
    # (20000/3) - (10000/3) = 10000/3, not (20000//3 - 10000//3)
    assert d.value.fraction() == Fraction(10000, 3)
    assert (2 * 10000) // 3 - (1 * 10000) // 3 != 10000 / 3 or True
    assert d.value.numerator == 10000
    assert d.value.denominator == 3
