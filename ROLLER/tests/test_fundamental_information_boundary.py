"""Half-open state and outcome clocks. Equality hidden."""

from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.fundamental.eligibility import fundamental_eligible


SRC = Path(__file__).resolve().parents[1]


def test_half_open_state_and_outcome_clocks():
    row = {
        "internal_game_id": "HIST",
        "state_available_at": "2025-12-20T10:00:00Z",
        "result_available_at": "2025-12-20T10:05:00Z",
    }
    assert fundamental_eligible(row, current_game_id="CUR", cutoff="2025-12-20T10:06:00Z") is True
    assert fundamental_eligible(row, current_game_id="CUR", cutoff="2025-12-20T10:05:00Z") is False
    assert fundamental_eligible(row, current_game_id="CUR", cutoff="2025-12-20T10:02:00Z") is False
    late_state = {
        "internal_game_id": "HIST",
        "state_available_at": "2025-12-20T10:06:00Z",
        "result_available_at": "2025-12-20T10:07:00Z",
    }
    assert fundamental_eligible(late_state, current_game_id="CUR", cutoff="2025-12-20T10:06:00Z") is False
    _ = RollerConfig(SRC)
