from __future__ import annotations

from fractions import Fraction

from roller.v4b.measurements import compute_observed
from tests.helpers_v4b import fund, make_xt


def test_theta_observed_is_delta_f_over_elapsed():
    xt = make_xt(
        f_t=fund(3, 4, "2025-12-20T20:15:00Z"),
        f_prev=fund(1, 2, "2025-12-20T20:13:00Z"),
        elapsed_t=780,
        elapsed_prev=720,
    )
    th = compute_observed(xt)["theta_observed"]
    assert th.status == "valid"
    assert th.extra["delta_elapsed_seconds"] == 60
    assert th.value.fraction() == Fraction(2500, 60)


def test_theta_null_when_elapsed_unchanged():
    xt = make_xt(elapsed_t=720, elapsed_prev=720)
    th = compute_observed(xt)["theta_observed"]
    assert th.value is None
    assert th.status == "ZERO_ELAPSED"
