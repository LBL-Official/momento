"""Support: unique games ≠ observation count. effective_n is null."""

from __future__ import annotations

from roller.measurement.support import support_object


def test_repeated_observations_are_not_independent_games():
    rows = [
        {"internal_game_id": "g1", "observation_time": "2025-12-20T20:00:00Z", "season": "2025-2026", "home_team_id": "BOS"},
        {"internal_game_id": "g1", "observation_time": "2025-12-20T20:05:00Z", "season": "2025-2026", "home_team_id": "BOS"},
        {"internal_game_id": "g2", "observation_time": "2025-12-21T20:00:00Z", "season": "2025-2026", "home_team_id": "LAL"},
    ]
    out = support_object(rows, min_unique_games=2, min_observations=3)
    assert out["n_observations"] == 3
    assert out["n_unique_games"] == 2
    assert out["n_observations"] != out["n_unique_games"]
    assert out["repeated_observation_warning"] is True
    assert out["effective_n"] is None
    assert out["effective_n_status"] == "NOT_IMPLEMENTED"
    assert out["sufficient"] is True
