"""Deterministic condition_id and config-driven buckets."""

from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.measurement.conditioning import condition_observation


SRC = Path(__file__).resolve().parents[1]


def _obs(**dims):
    return {
        "sport": "NBA",
        "GAME_STATE": {
            "data": {
                "period": dims.get("period", 3),
                "elapsed_game_seconds": dims.get("elapsed", 100),
                "score": {"score_differential_home": {"value": dims.get("margin", 2)}},
            }
        },
        "MARKET_STATE": {"data": {"yes_bid_close": dims.get("k", "5000")}},
        "BACKWARD_MEASUREMENTS": {
            "data": {"measurements": {"high_low_range_1m": {"value": dims.get("rng", 100)}}}
        },
        "POSSESSIONS": {"status": "REAL", "data": {"possessions": [{"end_status": "CONFIRMED"}]}},
    }


def test_same_state_same_condition_id():
    cfg = RollerConfig(SRC)
    a = condition_observation(cfg, _obs())
    b = condition_observation(cfg, _obs())
    assert a["condition_id"] == b["condition_id"]
    assert a["dimensions"]
    assert a["conditioning_schema_version"] == "conditioning_schema_v1"


def test_bucket_boundary_changes_id():
    cfg = RollerConfig(SRC)
    low = condition_observation(cfg, _obs(margin=-16))
    high = condition_observation(cfg, _obs(margin=-15))
    assert low["condition_id"] != high["condition_id"]
