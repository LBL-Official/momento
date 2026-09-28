from __future__ import annotations

from roller.v4b.measurements import compute_observed
from tests.helpers_v4b import fund, make_xt


def test_measurement_available_at_is_no_earlier_than_required_inputs():
    xt = make_xt(
        f_t=fund(3, 4, "2025-12-20T20:15:00Z"),
        f_prev=fund(1, 2, "2025-12-20T20:13:00Z"),
    )
    obs = compute_observed(xt)
    assert obs["market_delta_1m"].measurement_available_at == "2025-12-20T20:14:00Z"
    assert obs["fundamental_delta"].measurement_available_at == "2025-12-20T20:15:00Z"
    assert obs["response_delta"].measurement_available_at == "2025-12-20T20:15:00Z"
    assert obs["market_fundamental_basis"].measurement_available_at == "2025-12-20T20:15:00Z"
    assert obs["absolute_return"].measurement_available_at == obs["market_delta_1m"].measurement_available_at
