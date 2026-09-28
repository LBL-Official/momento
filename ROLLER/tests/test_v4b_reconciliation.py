from __future__ import annotations

from roller.v4b.measurements import RECONCILE_NAMES, _reconcile, compute_observed
from roller.v4b.types import ExactRational, MeasurementPoint
from tests.helpers_v4b import candle, fund, make_xt


def test_reconciliation_holds_exactly():
    xt = make_xt(
        current=candle("2025-12-20T20:14:00Z", 8000),
        previous=candle("2025-12-20T20:13:00Z", 7000),
        f_t=fund(3, 4, "2025-12-20T20:15:00Z"),
        f_prev=fund(1, 2, "2025-12-20T20:13:00Z"),
    )
    obs = compute_observed(xt)
    market = obs["market_delta_1m"].value
    fund_delta = obs["fundamental_delta"].value
    assert obs["response_delta"].value == market - fund_delta
    assert obs["basis_delta"].value == market - fund_delta
    assert obs["response_delta"].value == obs["basis_delta"].value


def test_reconciliation_failure_refuses_contradictory_numbers():
    bad = {
        "market_delta_1m": MeasurementPoint("market_delta_1m", ExactRational.from_int(100), "valid", "t"),
        "fundamental_delta": MeasurementPoint("fundamental_delta", ExactRational.from_int(10), "valid", "t"),
        "response_delta": MeasurementPoint("response_delta", ExactRational.from_int(90), "valid", "t"),
        "basis_delta": MeasurementPoint("basis_delta", ExactRational.from_int(91), "valid", "t"),
    }
    _reconcile(bad)
    assert bad["response_delta"].status == "RECONCILIATION_FAILED"
    assert bad["basis_delta"].status == "RECONCILIATION_FAILED"
    assert bad["response_delta"].value is None
    assert bad["basis_delta"].value is None
    assert set(RECONCILE_NAMES) >= {"market_delta_1m", "fundamental_delta", "response_delta", "basis_delta"}
