from __future__ import annotations

from pathlib import Path

from roller.admin import load_dataset
from roller.config import RollerConfig
from roller.features.engine import priors_before
from roller.maintenance.update import update_sport


def test_pre_game_and_rolling_exclude_current(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    feats = load_dataset(cfg, "NBA", "2025-2026", "team_features")
    g3 = feats[(feats["internal_game_id"] == "NBA_20251220_LAL_BOS") & (feats["team_id"] == "LAL")].iloc[0]
    assert int(g3["wins_pre"]) == 1
    assert int(g3["losses_pre"]) == 1
    assert int(g3["games_played_pre"]) == 2
    assert int(g3["wins_last_5_pre"]) == 1
    assert int(g3["losses_last_5_pre"]) == 1
    first = feats[(feats["internal_game_id"] == "NBA_20251210_LAL_BOS") & (feats["team_id"] == "LAL")].iloc[0]
    assert int(first["wins_pre"]) == 0
    assert int(first["games_played_pre"]) == 0


def test_unresolved_game_does_not_take_future_results():
    completed = [
        {
            "internal_game_id": "g1",
            "result_available_at": "2025-12-10T22:00:00Z",
            "won": True,
            "is_home": True,
            "game_date": "2025-12-10",
        },
        {
            "internal_game_id": "g3",
            "result_available_at": "2025-12-20T22:00:00Z",
            "won": True,
            "is_home": True,
            "game_date": "2025-12-20",
        },
    ]
    unresolved = {
        "internal_game_id": "g2",
        "result_available_at": "",
        "scheduled_start": "",
        "game_date": "2025-12-15",
    }
    priors = priors_before(completed, unresolved)
    assert [p["internal_game_id"] for p in priors] == ["g1"]
