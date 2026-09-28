"""Current game terminal outcome cannot enter F_t even after it is known."""

from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.fundamental.estimator import estimate_fundamental
from tests.helpers_v4a import fake_observation, stamped_row


SRC = Path(__file__).resolve().parents[1]


def test_current_game_outcome_cannot_change_estimate():
    cfg = RollerConfig(SRC)
    obs = fake_observation(gid="NBA_CUR", t="2025-12-20T21:00:00Z")
    priors = [
        stamped_row(cfg, gid="G1", state_at="2025-12-10T20:00:00Z", result_at="2025-12-10T22:00:00Z", home_win="1"),
        stamped_row(cfg, gid="G2", state_at="2025-12-11T20:00:00Z", result_at="2025-12-11T22:00:00Z", home_win="0"),
        stamped_row(cfg, gid="G3", state_at="2025-12-12T20:00:00Z", result_at="2025-12-12T22:00:00Z", home_win="1"),
    ]
    leak = stamped_row(
        cfg,
        gid="NBA_CUR",
        state_at="2025-12-20T20:14:00Z",
        result_at="2025-12-20T20:50:00Z",
        home_win="0",
    )
    clean = estimate_fundamental(cfg, observation=obs, corpus=priors)
    leaked = estimate_fundamental(cfg, observation=obs, corpus=priors + [leak])
    assert clean["status"] == "IMPLEMENTED"
    assert leaked["status"] == "IMPLEMENTED"
    assert "NBA_CUR" not in clean["eligible_internal_game_ids"]
    assert "NBA_CUR" not in leaked["eligible_internal_game_ids"]
    assert clean["value"] == leaked["value"]
    assert clean["probability_wins"] == 2
    assert clean["probability_n"] == 3
