from __future__ import annotations

from roller.v4b.measurements import compute_observed
from tests.helpers_v4b import candle, make_xt


def test_market_delta_signed_e4_on_60s_interval():
    xt = make_xt(
        current=candle("2025-12-20T20:14:00Z", 7500),
        previous=candle("2025-12-20T20:13:00Z", 7000),
    )
    m = compute_observed(xt)["market_delta_1m"]
    assert m.status == "valid"
    assert m.value.public() == {"numerator": 500, "denominator": 1, "units": "e4"}
    assert m.measurement_available_at == "2025-12-20T20:14:00Z"
    assert m.provenance["interval_seconds"] == 60
    assert m.provenance["expected_interval_seconds"] == 60
    assert m.path_information_status == "UNORDERED_SUMMARY"


def test_market_delta_negative():
    xt = make_xt(
        current=candle("2025-12-20T20:14:00Z", 6900),
        previous=candle("2025-12-20T20:13:00Z", 7400),
    )
    m = compute_observed(xt)["market_delta_1m"]
    assert m.value.numerator == -500
