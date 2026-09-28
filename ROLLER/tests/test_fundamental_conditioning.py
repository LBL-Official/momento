"""core_v1 only. Market and possession do not silently enter."""

from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.fundamental.conditioning import condition_observation, condition_state
from tests.helpers_v4a import fake_observation


SRC = Path(__file__).resolve().parents[1]


def test_core_v1_has_only_period_clock_score():
    cfg = RollerConfig(SRC)
    obs = fake_observation()
    cond = condition_observation(cfg, obs)
    assert cond["conditioning_schema_version"] == "core_v1"
    assert set(cond["raw_dimensions"]) == {"period", "clock_bucket", "score_margin_bucket"}
    assert "market_prob_bucket" not in cond["raw_dimensions"]
    assert "possession_status" not in cond["raw_dimensions"]
    assert cond["status"] == "valid"


def test_missing_clock_is_invalid():
    cfg = RollerConfig(SRC)
    cond = condition_state(cfg, {"period": 2, "elapsed_game_seconds": None, "score_differential_home": 3})
    assert cond["status"] == "INVALID_CONDITION"
    assert "clock_bucket" in cond["missing_dimensions"]
