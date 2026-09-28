"""Condition IDs are deterministic and retain raw dimensions."""

from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.fundamental.conditioning import condition_state
from roller.fundamental.estimator import estimate_fundamental
from tests.helpers_v4a import fake_observation, stamped_row


SRC = Path(__file__).resolve().parents[1]


def test_condition_id_stable_and_raw_dims_persisted():
    cfg = RollerConfig(SRC)
    a = condition_state(cfg, {"period": 4, "elapsed_game_seconds": 2700, "score_differential_home": 8})
    b = condition_state(cfg, {"period": 4, "elapsed_game_seconds": 2700, "score_differential_home": 8})
    assert a["condition_id"] == b["condition_id"]
    assert a["condition_id"].startswith("C_")
    assert a["raw_dimensions"]["period"] == "4"
    assert a["raw_dimensions"]["clock_bucket"] is not None
    assert a["raw_dimensions"]["score_margin_bucket"] is not None


def test_schema_change_is_a_distinct_estimator_identity():
    cfg = RollerConfig(SRC)
    obs = fake_observation()
    corpus = [
        stamped_row(cfg, gid="G1", state_at="2025-12-10T20:00:00Z", result_at="2025-12-10T22:00:00Z", home_win="1"),
        stamped_row(cfg, gid="G2", state_at="2025-12-11T20:00:00Z", result_at="2025-12-11T22:00:00Z", home_win="0"),
        stamped_row(cfg, gid="G3", state_at="2025-12-12T20:00:00Z", result_at="2025-12-12T22:00:00Z", home_win="1"),
    ]
    one = estimate_fundamental(cfg, observation=obs, corpus=corpus, conditioning_schema_version="core_v1")
    try:
        estimate_fundamental(cfg, observation=obs, corpus=corpus, conditioning_schema_version="core_plus_possession_v1")
        raised = False
    except KeyError:
        raised = True
    assert raised
    assert one["conditioning_schema_version"] == "core_v1"
