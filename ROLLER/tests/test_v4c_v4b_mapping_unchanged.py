"""V4C copies V4B rationals. No float compare. No new calculation."""

from __future__ import annotations

from pathlib import Path

from roller import Roller
from roller.config import RollerConfig
from roller.maintenance.update import update_sport
from roller.v4c import V4C_EMPIRICAL_COMPUTATION_COUNT
from roller.v4c.mapping import copy_rational, overlay_architecture
from roller.v4b.definitions import OBSERVED_FAMILIES


def test_copy_rational_is_integer_identity():
    src = {"numerator": 130, "denominator": 4, "units": "e4"}
    copied = copy_rational(src)
    assert copied["numerator"] == src["numerator"]
    assert copied["denominator"] == src["denominator"]
    assert copied["units"] == "e4"
    assert V4C_EMPIRICAL_COMPUTATION_COUNT == 0


def test_overlay_copies_v4b_numerators():
    cfg = RollerConfig(Path(__file__).resolve().parents[1])
    v4b = {
        "identity": {"observation_id": "OBS_TEST"},
        "observed": {
            "market_delta_1m": {
                "value": {"numerator": 17, "denominator": 1, "units": "e4"},
                "status": "valid",
            },
            "pure_theta": {"value": None, "status": "MIXED_INTERVAL"},
        },
        "availability": {"state_available_at": "2025-12-20T20:14:00Z"},
        "market": {"available_at": "2025-12-20T20:14:00Z"},
    }
    v4c = overlay_architecture(cfg, v4b)
    assert v4c["empirical_computation_count"] == 0
    market = v4c["measurements"]["market_delta_1m"]
    assert market["value"]["numerator"] == 17
    assert market["value"]["denominator"] == 1
    assert market["status"] == "IMPLEMENTED"
    assert v4c["measurements"]["pure_theta"]["value"] is None
    assert v4c["measurements"]["pure_theta"]["status"] == "INSUFFICIENT_SUPPORT"


def test_public_mapping_rational_identity(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    db = Roller(roller_env)
    obs = db.observation("NBA_20251220_LAL_BOS", as_of="2025-12-20T20:13:30Z")
    v4b = db.greeks(obs["observation_id"], corpus=[], schema_version="4.0.0-B")
    v4c = db.greeks(obs["observation_id"], corpus=[], schema_version="4.0.0-C")
    for name in OBSERVED_FAMILIES:
        src = v4b["observed"][name]
        mapped = v4c["measurements"][name]
        if src["value"] is None:
            assert mapped["value"] is None
        else:
            assert mapped["value"]["numerator"] == src["value"]["numerator"]
            assert mapped["value"]["denominator"] == src["value"]["denominator"]
