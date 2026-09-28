from __future__ import annotations

from roller.v4b.measurements import compute_observed
from tests.helpers_v4b import fund, make_xt


def test_delta_provenance_reconstructs_inputs():
    xt = make_xt(
        f_t=fund(3, 4, "2025-12-20T20:15:00Z"),
        f_prev=fund(1, 2, "2025-12-20T20:13:00Z"),
    )
    obs = compute_observed(xt)
    md = obs["market_delta_1m"].provenance
    assert md["current_available_at"] == "2025-12-20T20:14:00Z"
    assert md["previous_available_at"] == "2025-12-20T20:13:00Z"
    assert md["interval_seconds"] == 60
    assert md["expected_interval_seconds"] == 60
    fd = obs["fundamental_delta"].provenance
    assert fd["current_fundamental_cutoff"] == "2025-12-20T20:15:00Z"
    assert fd["prior_fundamental_cutoff"] == "2025-12-20T20:13:00Z"
    assert fd["current_numerator"] == 3
    assert fd["current_denominator"] == 4
    assert fd["prior_numerator"] == 1
    assert fd["prior_denominator"] == 2
