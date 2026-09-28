"""Future games cannot contribute to an earlier observation."""

from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.fundamental.estimator import estimate_fundamental
from tests.helpers_v4a import fake_observation, stamped_row


SRC = Path(__file__).resolve().parents[1]


def test_future_game_c_cannot_enter_earlier_estimate():
    cfg = RollerConfig(SRC)
    obs = fake_observation(gid="GAME_B", t="2025-12-15T20:14:00Z")
    a = stamped_row(cfg, gid="GAME_A", state_at="2025-12-10T20:00:00Z", result_at="2025-12-10T22:00:00Z", home_win="1")
    b_self = stamped_row(cfg, gid="GAME_B", state_at="2025-12-15T20:00:00Z", result_at="2025-12-15T22:00:00Z", home_win="0")
    c = stamped_row(cfg, gid="GAME_C", state_at="2025-12-20T20:00:00Z", result_at="2025-12-20T22:00:00Z", home_win="1")
    extra = stamped_row(cfg, gid="GAME_D", state_at="2025-12-11T20:00:00Z", result_at="2025-12-11T22:00:00Z", home_win="0")
    extra2 = stamped_row(cfg, gid="GAME_E", state_at="2025-12-12T20:00:00Z", result_at="2025-12-12T22:00:00Z", home_win="0")
    out = estimate_fundamental(cfg, observation=obs, corpus=[a, b_self, c, extra, extra2])
    assert out["status"] == "IMPLEMENTED"
    assert "GAME_C" not in out["eligible_internal_game_ids"]
    assert "GAME_B" not in out["eligible_internal_game_ids"]
    assert set(out["eligible_internal_game_ids"]) == {"GAME_A", "GAME_D", "GAME_E"}
    assert out["probability_wins"] == 1
    assert out["probability_n"] == 3
