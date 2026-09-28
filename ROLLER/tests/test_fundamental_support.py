"""Support object: unique games ≠ raw observations."""

from __future__ import annotations

from roller.fundamental.support import fundamental_support


def test_unique_games_are_not_observation_count():
    rows = [
        {"internal_game_id": "g1", "observation_time": "2025-12-10T20:00:00Z", "season": "2025-2026", "home_team_id": "BOS"},
        {"internal_game_id": "g1", "observation_time": "2025-12-10T20:05:00Z", "season": "2025-2026", "home_team_id": "BOS"},
        {"internal_game_id": "g1", "observation_time": "2025-12-10T20:10:00Z", "season": "2025-2026", "home_team_id": "BOS"},
        {"internal_game_id": "g2", "observation_time": "2025-12-11T20:00:00Z", "season": "2025-2026", "home_team_id": "LAL"},
    ]
    out = fundamental_support(
        rows,
        floors={
            "minimum_observations": 3,
            "minimum_unique_games": 2,
            "minimum_unique_dates": 1,
            "minimum_unique_seasons": 1,
        },
    )
    assert out["n_observations"] == 4
    assert out["n_unique_games"] == 2
    assert out["n_observations"] != out["n_unique_games"]
    assert out["repeated_observation_warning"] is True
    assert out["effective_n"] is None
    assert out["sufficient"] is True


def test_many_observations_one_game_is_insufficient():
    rows = [
        {
            "internal_game_id": "g1",
            "observation_time": f"2025-12-10T20:0{i}:00Z",
            "season": "2025-2026",
            "home_team_id": "BOS",
        }
        for i in range(5)
    ]
    out = fundamental_support(
        rows,
        floors={
            "minimum_observations": 3,
            "minimum_unique_games": 2,
            "minimum_unique_dates": 1,
            "minimum_unique_seasons": 1,
        },
    )
    assert out["n_observations"] >= 3
    assert out["n_unique_games"] == 1
    assert out["sufficient"] is False
