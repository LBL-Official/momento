"""1m candle measurements are not 1s L2 measurements."""

from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.measurement.registry import get_measurement


SRC = Path(__file__).resolve().parents[1]


def test_one_minute_and_one_second_are_distinct_identities():
    cfg = RollerConfig(SRC)
    one_m = get_measurement(cfg, "market_response_1m")
    one_s = get_measurement(cfg, "market_delta_1s_l2")
    assert one_m["source_resolution"] == "1m"
    assert one_s["source_resolution"] == "1s"
    assert one_m["measurement_name"] != one_s["measurement_name"]
    assert one_s["implementation_status"] == "SCHEMA_ONLY"
    assert one_m["information_boundary"] == "forward"
    assert one_s["information_boundary"] == "schema_only"
