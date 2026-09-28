"""Elapsed buckets from remaining ISO clock. Missing clock is not silently bucketed."""

from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.fundamental.conditioning import condition_state
from roller.state.clock import elapsed_game_seconds


SRC = Path(__file__).resolve().parents[1]


def test_elapsed_bucket_and_overtime():
    cfg = RollerConfig(SRC)
    q1_open = elapsed_game_seconds(1, "PT12M00S")
    assert q1_open == 0
    q4_two_min = elapsed_game_seconds(4, "PT02M00S")
    assert q4_two_min == 3 * 720 + (720 - 120)
    ot = elapsed_game_seconds(5, "PT05M00S")
    assert ot == 4 * 720
    a = condition_state(cfg, {"period": 1, "elapsed_game_seconds": q1_open, "score_differential_home": 0})
    b = condition_state(cfg, {"period": 1, "elapsed_game_seconds": 59, "score_differential_home": 0})
    c = condition_state(cfg, {"period": 1, "elapsed_game_seconds": 60, "score_differential_home": 0})
    assert a["raw_dimensions"]["clock_bucket"] == b["raw_dimensions"]["clock_bucket"]
    assert a["raw_dimensions"]["clock_bucket"] != c["raw_dimensions"]["clock_bucket"]
    missing = condition_state(cfg, {"period": 1, "elapsed_game_seconds": None, "score_differential_home": 0})
    assert missing["status"] == "INVALID_CONDITION"
