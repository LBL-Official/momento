"""Unsupported states return null, never 0.50 / market / global average."""

from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.fundamental.estimator import estimate_fundamental
from roller.fundamental.support import fundamental_support
from tests.helpers_v4a import fake_observation, stamped_row


SRC = Path(__file__).resolve().parents[1]


def test_insufficient_dates_refused():
    rows = [
        {"internal_game_id": "g1", "observation_time": "2025-12-10T20:00:00Z", "season": "2025-2026", "home_team_id": "BOS"},
        {"internal_game_id": "g2", "observation_time": "2025-12-10T21:00:00Z", "season": "2025-2026", "home_team_id": "LAL"},
        {"internal_game_id": "g3", "observation_time": "2025-12-10T22:00:00Z", "season": "2025-2026", "home_team_id": "NYK"},
    ]
    out = fundamental_support(
        rows,
        floors={
            "minimum_observations": 3,
            "minimum_unique_games": 2,
            "minimum_unique_dates": 2,
            "minimum_unique_seasons": 1,
        },
    )
    assert out["n_unique_games"] >= 2
    assert out["n_unique_dates"] == 1
    assert out["sufficient"] is False


def test_empty_cell_is_null_not_half():
    cfg = RollerConfig(SRC)
    obs = fake_observation(margin=40)
    prior = stamped_row(
        cfg, gid="G1", state_at="2025-12-10T20:00:00Z", result_at="2025-12-10T22:00:00Z", home_win="1", margin=-3
    )
    out = estimate_fundamental(cfg, observation=obs, corpus=[prior])
    assert out["value"] is None
    assert out["status"] == "INSUFFICIENT_SUPPORT"
    assert out["value"] != 0.5
    assert out["value"] != 0
    blob = str(out)
    assert "0.50" not in blob
    assert "yes_bid_close" not in blob
