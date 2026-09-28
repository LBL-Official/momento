from __future__ import annotations

from roller.v4b.measurements import compute_observed
from tests.helpers_v4b import fund, make_xt


def test_missing_f_does_not_fabricate_greeks():
    xt = make_xt(f_t=fund(1, 4, "2025-12-20T20:15:00Z", status="INSUFFICIENT_SUPPORT"))
    obs = compute_observed(xt)
    assert obs["market_delta_1m"].status == "valid"
    assert obs["absolute_return"].status == "valid"
    for name in (
        "fundamental_delta",
        "response_delta",
        "market_fundamental_basis",
        "basis_delta",
        "score_delta",
        "discrete_gamma",
        "theta_observed",
        "pure_theta",
    ):
        assert obs[name].value is None, name
        assert obs[name].status != "valid", name
