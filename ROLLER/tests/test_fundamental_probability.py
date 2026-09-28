"""Exact wins/n. No smoothing."""

from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.fundamental.estimator import estimate_fundamental
from tests.helpers_v4a import fake_observation, stamped_row


SRC = Path(__file__).resolve().parents[1]


def test_wins_over_n_is_exact():
    cfg = RollerConfig(SRC)
    obs = fake_observation()
    corpus = [
        stamped_row(cfg, gid="G1", state_at="2025-12-10T20:00:00Z", result_at="2025-12-10T22:00:00Z", home_win="1"),
        stamped_row(cfg, gid="G2", state_at="2025-12-11T20:00:00Z", result_at="2025-12-11T22:00:00Z", home_win="1"),
        stamped_row(cfg, gid="G3", state_at="2025-12-12T20:00:00Z", result_at="2025-12-12T22:00:00Z", home_win="0"),
        stamped_row(cfg, gid="G4", state_at="2025-12-13T20:00:00Z", result_at="2025-12-13T22:00:00Z", home_win="0"),
    ]
    out = estimate_fundamental(cfg, observation=obs, corpus=corpus)
    assert out["status"] == "IMPLEMENTED"
    assert out["probability_wins"] == 2
    assert out["probability_n"] == 4
    assert out["value"] == {"numerator": 2, "denominator": 4}
    assert out["contains_future_information"] is True
    assert out["effective_n"] is None


def test_public_api_uses_observation_id_time(roller_env: Path):
    from roller import Roller
    from roller.maintenance.update import update_sport

    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    db = Roller(roller_env)
    obs = db.observation("NBA_20251220_LAL_BOS", as_of="2025-12-20T20:13:30Z")
    from roller.fundamental.conditioning import condition_observation
    from tests.helpers_v4a import stamped_row

    cond = condition_observation(cfg, obs)
    if cond["status"] != "valid":
        return
    dims = cond["raw_dimensions"]
    period = int(dims["period"])
    elapsed = int(dims["clock_bucket"])
    # Reconstruct a matching margin in the same score bucket via the observation state.
    from roller.fundamental.conditioning import observation_state_fields

    margin = observation_state_fields(obs)["score_differential_home"]
    corpus = [
        stamped_row(
            cfg,
            gid="HIST1",
            state_at="2025-12-10T20:00:00Z",
            result_at="2025-12-10T22:00:00Z",
            home_win="1",
            period=period,
            elapsed=elapsed,
            margin=int(margin),
        ),
        stamped_row(
            cfg,
            gid="HIST2",
            state_at="2025-12-11T20:00:00Z",
            result_at="2025-12-11T22:00:00Z",
            home_win="1",
            period=period,
            elapsed=elapsed,
            margin=int(margin),
        ),
        stamped_row(
            cfg,
            gid="HIST3",
            state_at="2025-12-12T20:00:00Z",
            result_at="2025-12-12T22:00:00Z",
            home_win="0",
            period=period,
            elapsed=elapsed,
            margin=int(margin),
        ),
    ]
    out = db.fundamental(obs["observation_id"], corpus=corpus)
    assert out["observation_id"] == obs["observation_id"]
    assert out["status"] == "IMPLEMENTED"
    assert out["probability_n"] == 3
