from __future__ import annotations

from fractions import Fraction

from roller.v4b.measurements import compute_observed
from tests.helpers_v4b import fund, make_xt


def test_score_delta_uses_home_minus_away():
    xt = make_xt(
        f_t=fund(3, 4, "2025-12-20T20:15:00Z"),
        f_prev=fund(1, 2, "2025-12-20T20:13:00Z"),
        s_t=2,
        s_prev=-1,
    )
    s = compute_observed(xt)["score_delta"]
    assert s.status == "valid"
    assert s.extra["delta_s"] == 3
    assert s.value.fraction() == Fraction(2500, 3)
    assert s.value.units == "e4_per_score_point"


def test_score_delta_null_when_delta_s_zero():
    xt = make_xt(s_t=4, s_prev=4)
    s = compute_observed(xt)["score_delta"]
    assert s.value is None
    assert s.status == "ZERO_SCORE_DELTA"
