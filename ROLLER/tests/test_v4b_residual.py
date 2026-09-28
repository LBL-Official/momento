from __future__ import annotations

from roller.v4b.residual import compute_residual
from roller.v4b.types import ExactRational, MeasurementPoint


def test_residual_is_m_minus_expected():
    observed = MeasurementPoint(
        "market_delta_1m",
        ExactRational.from_int(250),
        "valid",
        "2025-12-20T20:14:00Z",
    )
    baseline = {
        "status": "valid",
        "expected": {"numerator": 200, "denominator": 1, "units": "e4"},
        "dispersion": {"kind": "mean_absolute_deviation", "numerator": 10, "denominator": 1, "units": "e4"},
        "support": {"sufficient": True, "n_observations": 3, "n_unique_games": 3},
    }
    r = compute_residual(observed, baseline)
    assert r["status"] == "valid"
    assert r["value"] == {"numerator": 50, "denominator": 1, "units": "e4"}
    assert r["measurement_available_at"] == "2025-12-20T20:14:00Z"


def test_residual_insufficient_is_null_not_zero():
    observed = MeasurementPoint("market_delta_1m", ExactRational.from_int(250), "valid", "t")
    r = compute_residual(observed, {"status": "INSUFFICIENT_SUPPORT", "support": {"sufficient": False}})
    assert r["value"] is None
    assert r["status"] == "INSUFFICIENT_SUPPORT"
    assert r["value"] != 0
