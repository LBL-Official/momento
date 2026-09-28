"""Same inputs produce the same F_t."""

from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.fundamental.estimator import estimate_fundamental
from tests.helpers_v4a import fake_observation, stamped_row


SRC = Path(__file__).resolve().parents[1]


def test_repeated_query_is_identical():
    cfg = RollerConfig(SRC)
    obs = fake_observation()
    corpus = [
        stamped_row(cfg, gid="G1", state_at="2025-12-10T20:00:00Z", result_at="2025-12-10T22:00:00Z", home_win="1"),
        stamped_row(cfg, gid="G2", state_at="2025-12-11T20:00:00Z", result_at="2025-12-11T22:00:00Z", home_win="0"),
        stamped_row(cfg, gid="G3", state_at="2025-12-12T20:00:00Z", result_at="2025-12-12T22:00:00Z", home_win="1"),
    ]
    a = estimate_fundamental(cfg, observation=obs, corpus=corpus)
    b = estimate_fundamental(cfg, observation=obs, corpus=corpus)
    assert a["value"] == b["value"]
    assert a["condition_id"] == b["condition_id"]
    assert a["status"] == b["status"]
    assert a["eligible_internal_game_ids"] == b["eligible_internal_game_ids"]
    assert a["n_unique_games"] == b["n_unique_games"]
    assert a["fundamental_id"] == b["fundamental_id"]
    assert a["calculated_at"] == a["information_cutoff"]
