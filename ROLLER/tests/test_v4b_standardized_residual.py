from __future__ import annotations

from fractions import Fraction

from roller.v4b.residual import compute_residual, standardized_residual
from roller.v4b.types import ExactRational, MeasurementPoint


def test_standardized_residual_only_when_mad_positive():
    observed = MeasurementPoint("market_delta_1m", ExactRational.from_int(250), "valid", "t")
    baseline = {
        "status": "valid",
        "expected": {"numerator": 200, "denominator": 1, "units": "e4"},
        "dispersion": {"kind": "mean_absolute_deviation", "numerator": 25, "denominator": 1, "units": "e4"},
        "support": {"sufficient": True},
    }
    r = compute_residual(observed, baseline)
    assert r["standardized"] == {"numerator": 2, "denominator": 1, "units": "mad_units"}


def test_standardized_residual_null_when_mad_zero():
    observed = MeasurementPoint("market_delta_1m", ExactRational.from_int(250), "valid", "t")
    baseline = {
        "status": "valid",
        "expected": {"numerator": 250, "denominator": 1, "units": "e4"},
        "dispersion": {"kind": "mean_absolute_deviation", "numerator": 0, "denominator": 1, "units": "e4"},
        "support": {"sufficient": True},
    }
    r = compute_residual(observed, baseline)
    assert r["value"] == {"numerator": 0, "denominator": 1, "units": "e4"}
    assert r["standardized"] is None
    assert r.get("standardized_status") == "MAD_ZERO"
    assert standardized_residual(Fraction(1), Fraction(0)) is None
