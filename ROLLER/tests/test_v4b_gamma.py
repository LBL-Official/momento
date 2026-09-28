from __future__ import annotations

from roller.v4b.measurements import compute_observed
from tests.helpers_v4b import candle, fund, make_xt


def test_discrete_gamma_is_temporal_second_difference():
    xt = make_xt(
        current=candle("2025-12-20T20:14:00Z", 7500),
        previous=candle("2025-12-20T20:13:00Z", 7400),
        previous2=candle("2025-12-20T20:12:00Z", 7300),
        f_t=fund(8, 10, "2025-12-20T20:15:00Z"),
        f_prev=fund(6, 10, "2025-12-20T20:13:00Z"),
        f_prev2=fund(5, 10, "2025-12-20T20:12:00Z"),
    )
    g = compute_observed(xt)["discrete_gamma"]
    # ΔF_t = 2000, ΔF_{t-1} = 1000, gamma = 1000
    assert g.status == "valid"
    assert g.value.fraction() == 1000
    assert g.provenance["kind"] == "temporal_second_difference"


def test_discrete_gamma_requires_compatible_intervals():
    xt = make_xt(
        current=candle("2025-12-20T20:14:00Z", 7500),
        previous=candle("2025-12-20T20:13:00Z", 7400),
        previous2=candle("2025-12-20T20:11:00Z", 7300),
        f_t=fund(8, 10, "2025-12-20T20:15:00Z"),
        f_prev=fund(6, 10, "2025-12-20T20:13:00Z"),
        f_prev2=fund(5, 10, "2025-12-20T20:11:00Z"),
    )
    g = compute_observed(xt)["discrete_gamma"]
    assert g.value is None
    assert g.status == "PERIOD_OR_SEQUENCE_GAP"
